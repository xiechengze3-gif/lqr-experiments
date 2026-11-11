"""Standard-library resource planner/submission guard; no numerical simulations."""
import argparse
import hashlib
import json
import math
import subprocess
from collections import defaultdict
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2)+'\n')
    temp.replace(path)


def plan(release, output, balance):
    cfg = read(release/'manifest.json')
    proof = read(output/'benchmark/benchmark.json')
    assert proof['status']=='PASS' and proof['identity']==sha(release/'manifest.json')
    assert proof['npg_checkpoint_replay']['status']=='PASS'
    assert proof['peak_process_RSS_KiB'] < 1024*1024, 'Reassess 2G memory before production'
    timings = {(t['n'], t['algorithm']):t for t in proof['timings']}
    rates, actual_pilot = {}, []
    for n in (50, 100):
        directory = output/f'benchmark/pilot-n{n}-Direct_Stein_PI/tasks'
        pi_actual = sum(read(p)['meta']['actual_transitions'] for p in directory.glob('*/core/n*.json'))
        assert pi_actual > 0
        pi_small = timings[n, 'Direct_Stein_PI']
        pi_large = timings[n, 'PI_max_batch']
        # A failed pilot can execute less than planned. Extrapolate from the
        # actual executed count, never the optimistic nominal denominator.
        rates[n, 'Direct_Stein_PI'] = max(pi_small['seconds']/pi_actual,
                                         pi_large['seconds']/pi_large['sampled_transitions'])
        npg_actual = read(output/f'benchmark/pilot-n{n}-npg/result.json')['actual_transitions']
        rates[n, 'NPG'] = timings[n, 'NPG']['seconds']/npg_actual
        ce_files = list((output/f'benchmark/pilot-n{n}-CE/tasks').glob('*/result.json'))
        assert len(ce_files)==1
        ce_actual = read(ce_files[0])['actual_transitions']
        rates[n, 'CE'] = timings[n, 'CE']['seconds']/ce_actual
        actual_pilot.append(dict(n=n, PI_actual_transitions=pi_actual, NPG_actual_transitions=npg_actual,
                                 CE_actual_transitions=ce_actual))
    groups = defaultdict(list)
    for task in cfg['tasks']:
        groups[task['algorithm'], task['n'], task.get('blocks', 0)].append(task)
    jobs = []
    for index, ((algorithm, n, blocks), tasks) in enumerate(sorted(groups.items())):
        seconds = max(t['planned_transitions']*rates[n, algorithm] for t in tasks)
        # Include compilation/startup overhead for every array element; no
        # speedup credit from pilot failures or shared Numba compilation.
        minutes = max(5, math.ceil((2*seconds+60)/300)*5)
        assert minutes <= 24*60, 'Task needs an explicit stage-chunk resource plan'
        jobs.append(dict(group=index, algorithm=algorithm, n=n, blocks=blocks,
                         indices=[t['id'] for t in tasks], tasks=len(tasks), cores=1, memory='2G',
                         partition='short' if minutes<=120 else 'medium',
                         wall_minutes=minutes, max_concurrent=2 if algorithm=='Direct_Stein_PI' else 1,
                         predicted_cpu_hours=len(tasks)*seconds/3600,
                         reserved_SU=len(tasks)*minutes/60,
                         seconds_per_transition_measured=rates[n, algorithm]))
    reserved = sum(g['reserved_SU'] for g in jobs)
    predicted = sum(g['predicted_cpu_hours'] for g in jobs)
    # Account/node query must separately confirm 2G <= one memory-equivalent
    # core on the selected current Grace nodes, and the current available
    # balance must already exclude other jobs' reservations.
    assert reserved <= cfg['budget']['production_SU_ceiling'], (reserved, cfg['budget'])
    assert reserved+1 <= balance, (reserved, balance)
    result = dict(status='READY_FOR_SUBMISSION', manifest_sha256=sha(release/'manifest.json'),
                  planner_sha256=sha(Path(__file__)), benchmark_job=proof['slurm_job_id'],
                  available_balance_SU=balance, predicted_actual_SU=predicted,
                  production_reserved_SU_ceiling=reserved, report_reserved_SU=1.,
                  combined_production_and_report_reserved_SU=reserved+1,
                  benchmark_pilot_actual_counts=actual_pilot,
                  effective_cores_assumption='1; current Grace 48 CPUs/368640MiB nodes, 2G request',
                  retry_limit=0, total_tasks=sum(g['tasks'] for g in jobs),
                  max_simultaneous_cores=sum(g['max_concurrent'] for g in jobs), groups=jobs)
    atomic(output/'production_resource_plan.json', result)
    print(json.dumps(result))


def submit(release, output, account):
    import fcntl
    cfg = read(release/'manifest.json')
    resources = read(output/'production_resource_plan.json')
    assert resources['manifest_sha256']==sha(release/'manifest.json')
    assert resources['total_tasks']==len(cfg['tasks'])
    assert resources['production_reserved_SU_ceiling']<=cfg['budget']['production_SU_ceiling']
    guard = output/'production_submission.lock'
    with guard.open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt_path = output/'production_submission.json'
        if receipt_path.exists():
            raise FileExistsError('A submission receipt already exists; inspect it rather than duplicating arrays')
        receipt = dict(state='SUBMITTING', manifest_sha256=resources['manifest_sha256'], account=account,
                       resource_plan_sha256=sha(output/'production_resource_plan.json'), arrays=[])
        atomic(receipt_path, receipt)
        for group in resources['groups']:
            minutes = group['wall_minutes']
            command = ['sbatch', '--parsable', '--account='+account, '--partition='+group['partition'],
                       '--ntasks=1', '--cpus-per-task=1', '--mem=2G', '--no-requeue',
                       '--time='+f'{minutes//60:02d}:{minutes%60:02d}:00',
                       '--job-name='+f"lqr-align-{group['group']}",
                       '--array='+','.join(map(str, group['indices']))+'%'+str(group['max_concurrent']),
                       '--output='+str(output/'logs/task-%A-%a.log'),
                       str(release/'slurm/aligned_extension.sbatch'), str(release), str(output), 'run']
            raw = subprocess.check_output(command, text=True).strip()
            assert raw.isdigit(), raw
            receipt['arrays'].append(dict(group=group['group'], job_id=raw, task_count=group['tasks'],
                                          algorithm=group['algorithm'], n=group['n'], blocks=group['blocks']))
            atomic(receipt_path, receipt)
        dependency = 'afterany:'+':'.join(g['job_id'] for g in receipt['arrays'])
        command = ['sbatch', '--parsable', '--account='+account, '--partition=short', '--ntasks=1',
                   '--cpus-per-task=1', '--mem=2G', '--time=01:00:00', '--no-requeue',
                   '--job-name=lqr-align-report', '--dependency='+dependency,
                   '--output='+str(output/'logs/report-%j.log'),
                   str(output/'control/aligned_complete.sbatch'), str(release), str(output)]
        receipt['report_job'] = subprocess.check_output(command, text=True).strip()
        assert receipt['report_job'].isdigit()
        receipt['state'] = 'SUBMITTED'
        atomic(receipt_path, receipt)
        print(json.dumps(receipt))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode', choices=['plan','submit'])
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--balance', type=float)
    parser.add_argument('--account')
    args=parser.parse_args()
    if args.mode=='plan':
        plan(args.release, args.output, args.balance)
    else:
        assert args.account and args.account.isdigit()
        submit(args.release, args.output, args.account)
