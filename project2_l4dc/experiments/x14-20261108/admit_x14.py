"""Quota and cost admission on Grace, with exclusive submission receipts."""
import argparse
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


SCRATCH = '/scratch/user/changze'
ROOT = Path(SCRATCH + '/lqr_experiments/tmp/x14-20261108')
ACCOUNT = '132685389143'
TASKS = {('a', 'pilot'): 4, ('a', 'formal'): 64, ('b', 'pilot'): 8, ('b', 'formal'): 256}
REPORT_RESERVE = 4


def call(*command):
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def allocations(job):
    raw = call('sacct', '-X', '--array', '-n', '-P', '-j', job,
               '--format=JobID,State%35,ElapsedRaw,AllocTRES,ExitCode')
    rows = []
    for line in raw.splitlines():
        jid, state, secs, alloc, code = line.split('|')[:5]
        if not re.fullmatch(job + r'_\d+', jid):
            continue
        charge = next((int(x[8:]) for x in alloc.split(',') if x.startswith('billing=')), None)
        rows.append(dict(id=jid, state=state, elapsed_seconds=int(secs), billing=charge, exitcode=code))
    return rows


def history():
    receipts = [read(p) for p in sorted(ROOT.glob('submit-*-DONE.json'))]
    result = []
    settled, outstanding, historical = 0., 0., 0.
    for receipt in receipts:
        rows = allocations(receipt['job'])
        assert len(rows) <= receipt['tasks']
        complete = [r for r in rows if r['state'] in {'COMPLETED','FAILED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','CANCELLED','PREEMPTED'}]
        assert all(r['billing'] == 1 for r in complete)
        assert all(r['state'] == 'COMPLETED' and r['exitcode'] == '0:0' for r in complete), complete
        settled += sum(r['elapsed_seconds']/3600 for r in complete)
        outstanding += (receipt['tasks']-len(complete))*receipt['minutes']/60
        historical += receipt['tasks']*receipt['minutes']/60
        result.append(dict(receipt, allocations=rows))
    return dict(settled_SU=settled, outstanding_upper_SU=outstanding,
                historical_requested_SU=historical, report_reserve_SU=REPORT_RESERVE, jobs=result)


def quota(files, size):
    placement = call('lfs', 'getdirstripe', '-i', str(ROOT)).strip()
    assert placement in {'0','1'} and call('lfs','getstripe','-m',str(ROOT/'placement.txt')).strip() == placement
    raw = call('lfs','quota','-v','-p','231181',SCRATCH)
    overall = next(line.split() for line in raw.splitlines() if line.strip().startswith(SCRATCH+' '))
    targets = [next(line.split() for line in raw.splitlines() if f'fs01-MDT000{i}' in line) for i in (0,1)]
    df_bytes = call('df','-B1','--output=avail',str(ROOT))
    df_files = call('df','--output=iavail',str(ROOT))
    available_files = min(int(overall[7])-int(overall[5]), int(df_files.splitlines()[-1]),
                          *(int(mdt[7])-int(mdt[5]) for mdt in targets))
    available_bytes = min((int(overall[3])-int(overall[1]))*1024, int(df_bytes.splitlines()[-1]))
    mdt_bytes = min((int(mdt[3])-int(mdt[1]))*1024 for mdt in targets)
    assert files < .8*available_files and size < .8*available_bytes and files*65536 < .8*mdt_bytes, (
        files, size, available_files, available_bytes, mdt_bytes)
    return dict(placement=placement, raw_project_quota=raw, quota_aware_df_bytes=df_bytes,
                quota_aware_df_files=df_files, effective_slots=available_files, available_bytes=available_bytes,
                mdt_available_metadata_bytes=mdt_bytes, forecast_files=files, forecast_bytes=size)


def pilot_plan(item):
    count = TASKS[item, 'pilot']
    prior = read(ROOT/f'submit-{item}-pilot-DONE.json')
    rows = allocations(prior['job'])
    assert len(rows) == count and all(r['state']=='COMPLETED' and r['exitcode']=='0:0' for r in rows)
    metrics = []
    for i in range(count):
        prefix = f'x14{item}-pilot-{i:03d}'
        archive, journal = ROOT/(prefix+'.tar'), ROOT/(prefix+'.jsonl')
        final = json.loads(journal.read_bytes().splitlines()[-1])
        assert final['kind']=='TASK_FINAL' and final['status']=='COMPLETE'
        assert all(c['status']=='PASS_BITWISE_GAINS_COLLECTOR_RNG_COUNTS' for c in final['equivalence'])
        assert len(final['equivalence']) == 2 and final['peak_RSS_KiB'] <= .8*2*1024**2
        assert final['archive_bytes'] == archive.stat().st_size and final['physical_store_files']==2
        metrics.append(dict(index=i, body_seconds=final['body_seconds'], peak_RSS_KiB=final['peak_RSS_KiB'],
                            archive_bytes=final['archive_bytes'], journal_bytes=journal.stat().st_size,
                            paths=len(final['paths']), sha256=final['archive_sha256']))
    body = max(row['body_seconds'] for row in metrics)
    return dict(metrics=metrics, body_seconds=body, minutes=math.ceil((1.2*body+30)/60),
                forecast_task_bytes=math.ceil(1.5*max(x['archive_bytes']+x['journal_bytes'] for x in metrics))+2**20)


def main(a):
    assert ROOT.is_dir() and call('id','-un').strip() == 'changze'
    key = f'{a.item}-{a.stage}'
    begin = ROOT/f'submit-{key}-BEGIN.json'
    end = ROOT/f'submit-{key}-DONE.json'
    response = ROOT/f'submit-{key}-RESPONSE.json'
    assert not any(p.exists() for p in (begin,end,response)), 'Reconcile earlier attempt before any mutation.'
    assert not call('sacct','-X','-n','-P','-u','changze','-S','2026-11-08','--name=x14-'+key,'--format=JobID').strip()
    books = history()
    assert books['outstanding_upper_SU']==0, 'Complete preceding X14 stage first.'
    tasks = TASKS[a.item,a.stage]
    if a.stage == 'pilot':
        minutes, timing = (15 if a.item == 'a' else 10), None
    else:
        timing = pilot_plan(a.item)
        minutes = timing['minutes']
    requested = tasks*minutes/60
    body = requested if timing is None else (timing['body_seconds']+30)*tasks/3600
    # Include plausible remaining registered work for the initial planning gate.
    future_estimate = {('a','pilot'):42, ('a','formal'):32, ('b','pilot'):21, ('b','formal'):6}[a.item,a.stage]
    expected_actual = books['settled_SU'] + body + future_estimate + REPORT_RESERVE
    exposure = books['settled_SU']+books['outstanding_upper_SU']+requested+REPORT_RESERVE
    assert expected_actual<=60 and exposure<=80, (expected_actual,exposure)
    balance = call('myproject')
    account = next(line.split('|') for line in balance.splitlines() if '|'+ACCOUNT+'|' in line)
    assert float(account[6]) >= requested+REPORT_RESERVE
    queue = call('squeue','-r','-h','-u','changze','-o','%i %T')
    running_or_pending = len(queue.splitlines())
    throttle = min(64-running_or_pending,tasks)
    assert 1<=throttle<=64
    size = 48*2**20 if timing is None else timing['forecast_task_bytes']
    fs = quota(24*tasks+128, (size+64*2**20)*tasks+256*2**20)
    script = ROOT/f'{key}.sbatch'
    assert script.is_file()
    command = ['sbatch','--parsable',f'--account={ACCOUNT}','--partition=medium','--ntasks=1','--cpus-per-task=1',
               '--mem=2048M',f'--time={minutes}','--no-requeue',f'--job-name=x14-{key}',
               f'--array=0-{tasks-1}%{throttle}',f'--output={ROOT}/x14{a.item}-{a.stage}-%A_%a.out',str(script)]
    receipt = dict(item=a.item, stage=a.stage, tasks=tasks, minutes=minutes, utc=datetime.now(timezone.utc).isoformat(),
                   requested_SU=requested, expected_actual_SU=expected_actual, exposure_SU=exposure,
                   books=books, timing=timing, quota=fs, balance=balance, own_queue=queue, command=command)
    if a.check:
        print(json.dumps(receipt))
        return
    write(begin, receipt)
    job = subprocess.run(command, text=True, capture_output=True)
    write(response, dict(returncode=job.returncode, stdout=job.stdout, stderr=job.stderr))
    assert job.returncode==0 and re.fullmatch(r'\d+(;\S+)?',job.stdout.strip()), 'Reconcile Slurm state before further action.'
    result = dict(receipt, job=job.stdout.strip().split(';')[0], status='SUBMITTED_ONCE')
    write(end, result)
    print(json.dumps({k:result[k] for k in ('status','job','tasks','minutes','requested_SU','expected_actual_SU','exposure_SU')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('item',choices=['a','b'])
    parser.add_argument('stage',choices=['pilot','formal'])
    parser.add_argument('--check',action='store_true')
    main(parser.parse_args())
