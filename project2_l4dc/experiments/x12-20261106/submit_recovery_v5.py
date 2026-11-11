"""Quota and SU admission for X12. Each mutation has an exclusive receipt."""
import argparse
import datetime
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path


USER = 'changze'
ACCOUNT = '132685389143'
SCRATCH = '/scratch/user/changze'
ROOT = Path(SCRATCH) / 'lqr_experiments/tmp/x12-storage-recovery-20261107-v6'
SOURCE = Path('/scratch/user/changze/lqr_experiments/results/x12-20261106')
PYTHON = '/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python'
CAP_ACTUAL, CAP_EXPOSURE, RESERVE = 230, 300, 8
BASE_HISTORICAL_REQUESTS = 169.9
START = '2026-11-06T00:00:00'


def call(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def read(p):
    return json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write(p, obj):
    with p.open('x', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)
        f.write('\n')


def rows(job):
    raw = call(['sacct','-X','--array','-n','-P','-j',str(job),'--format=JobID,State%40,ElapsedRaw,AllocTRES,ExitCode'])
    result = []
    for line in raw.splitlines():
        if not line:
            continue
        jid, state, secs, tres, exitcode = line.split('|')[:5]
        t = dict(s.split('=',1) for s in tres.split(',') if '=' in s)
        assert int(t['billing']) == int(t['cpu']) == 1, (jid, tres)
        result.append(dict(job=jid, state=state, elapsed_seconds=int(secs), actual_SU=int(secs)/3600, exitcode=exitcode))
    assert len({r['job'] for r in result}) == len(result)
    return result


def history(pilot):
    old = read(SOURCE / 'budget/LEDGER_v10.json')
    assert abs(old['cumulative_requested_SU'] - BASE_HISTORICAL_REQUESTS) < 1e-8
    result = []
    for e in old['allocations']:
        r = rows(e['job'])
        assert len(r) == e['tasks'] and all(x['state'] in ('COMPLETED','FAILED') for x in r)
        result.extend(r)
    assert len(result) == 76 and sum(r['state'] == 'FAILED' for r in result) == 64
    bad, good = rows('20424737'), rows(pilot)
    assert len(bad) == len(good) == 1 and bad[0]['state'] == 'FAILED' and bad[0]['elapsed_seconds'] == 16
    assert good[0]['state'] == 'COMPLETED' and good[0]['exitcode'] == '0:0'
    return result + bad + good


def quota(root, forecast_files, forecast_bytes):
    assert call(['lfs','getdirstripe','-i',str(root)]).strip() == '1'
    assert call(['lfs','getstripe','-m',str(root/'placement-probe.txt')]).strip() == '1'
    q = call(['lfs','quota','-v','-p','231181',SCRATCH])
    qtotal = next(line.split() for line in q.splitlines() if line.strip().startswith(SCRATCH + ' '))
    qmdt = next(line.split() for line in q.splitlines() if 'fs01-MDT0001' in line)
    raw_files = int(qtotal[7])-int(qtotal[5])
    raw_bytes = (int(qtotal[3])-int(qtotal[1])) * 1024
    mdt_files = int(qmdt[7])-int(qmdt[5])
    mdt_bytes = (int(qmdt[3])-int(qmdt[1])) * 1024
    db = call(['df','-B1','--output=avail',str(root)])
    di = call(['df','--output=iavail',str(root)])
    free_bytes = min(raw_bytes, int(db.splitlines()[-1].strip()))
    free_files = min(raw_files, int(di.splitlines()[-1].strip()), mdt_files)
    assert forecast_files < .8 * free_files, (forecast_files, free_files, q)
    assert forecast_bytes < .8 * free_bytes, (forecast_bytes, free_bytes, q)
    assert forecast_files * 32 * 1024 < .8 * mdt_bytes, (forecast_files, mdt_bytes, q)
    return dict(utc=now(), project=231181, mdt=1, raw_quota=q, quota_aware_df_bytes=db, quota_aware_df_files=di,
                effective_free_files=free_files, effective_free_bytes=free_bytes, MDT1_free_files=mdt_files,
                MDT1_free_metadata_bytes=mdt_bytes, required_files=forecast_files, required_bytes=forecast_bytes)


def queue(allowed=()):
    q = call(['squeue','-r','-h','-u',USER,'-o','%i']).splitlines()
    ids = {j.strip() for j in q if j.strip()}
    assert len(ids) <= 32 * len(allowed) and all(j.split('_')[0] in allowed for j in ids), ids
    return sorted(ids)


def balance(needed):
    s = call(['myproject'])
    a = next(line for line in s.splitlines() if f'|{ACCOUNT}|' in line)
    assert float(a.split('|')[6]) >= needed
    return a


def wrap(root, mode, group=None):
    # This string is shell code. All variable paths below are fixed or quoted.
    env = '''set -eu
umask 077
node=/tmp/changze-x12-recovery-v5-${SLURM_JOB_ID:?}-${SLURM_ARRAY_TASK_ID:-report}
mkdir "$node"
mkdir "$node/tmp" "$node/cache"
export TMPDIR="$node/tmp" TMP="$node/tmp" TEMP="$node/tmp" XDG_CACHE_HOME="$node/cache"
export NUMBA_CACHE_DIR="$node/cache/numba" MPLCONFIGDIR="$node/cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
'''
    cfg, bundle = shlex.quote(str(root/'recovery-config.json')), shlex.quote(str(root/'recovery-v5.zip'))
    release = read(root/'RECOVERY_RELEASE_MANIFEST_v5.json')
    env += f"printf '%s  %s\\n' {release['config_sha256']} {cfg} {release['bundle_sha256']} {bundle} | sha256sum -c - >/dev/null\n"
    cmd = f'exec {PYTHON} -B {bundle} {mode} --config {cfg}'
    if mode == 'formal':
        assert group in ('n60-nine-NPG', 'n60-nine-PI')
        cmd += f' --output {shlex.quote(str(root))} --group {group} --index "$SLURM_ARRAY_TASK_ID"'
    else:
        assert mode == 'report' and group is None
        cmd += f' --root {shlex.quote(str(root))}'
    return env + cmd + '\n'


def submit(root, role, minutes, q, accounting, mode, group=None):
    name = 'x12-rec-v5-' + role
    assert not call(['sacct','-X','-n','-P','--array','-u',USER,'-S',START,'--name='+name,'--format=JobID']).strip()
    begin, response, done = [root/f'{name}-{tag}.json' for tag in ('BEGIN','RESPONSE','DONE')]
    assert not any(x.exists() for x in (begin,response,done)), 'Existing attempt; never replay.'
    part = call(['scontrol','show','partition','medium','-o'])
    assert 'State=UP' in part
    args = ['sbatch','--parsable','--account='+ACCOUNT,'--partition=medium','--ntasks=1','--cpus-per-task=1',
            '--mem=2048M','--time='+str(minutes),'--no-requeue','--job-name='+name,
            '--output='+str(root/(name+('-%A_%a.out' if group else '-%j.out')))]
    if group:
        args.append('--array=0-31%32')
    args += ['--wrap',wrap(root,mode,group)]
    write(begin, dict(utc=now(), command=args, latest_quota=q, accounting=accounting, retries=0))
    r = subprocess.run(args, capture_output=True, text=True)
    write(response, dict(returncode=r.returncode, stdout=r.stdout, stderr=r.stderr))
    assert r.returncode == 0 and re.fullmatch(r'\d+(;[^\s]+)?', r.stdout.strip()), 'Reconcile; do not retry.'
    receipt = dict(status='SUBMITTED_ONCE', job=r.stdout.strip().split(';')[0], utc=now(), role=role,
                   requested_SU=minutes*(32 if group else 1)/60, automatic_retries=0)
    write(done, receipt)
    print(json.dumps(receipt), flush=True)
    return receipt


def release(root, cfgsha, bundle_sha):
    assert root == ROOT and root.is_dir()
    rm = read(root/'RECOVERY_RELEASE_MANIFEST_v5.json')
    assert rm['status'] == 'LOCAL_RECOVERY_RELEASE_READY_NOT_SUBMITTED'
    assert cfgsha == rm['config_sha256'] == sha(root/'recovery-config.json')
    assert bundle_sha == rm['bundle_sha256'] == sha(root/'recovery-v5.zip')
    cfg = read(root/'recovery-config.json')['recovery']
    assert cfg['status'] == 'READY_FOR_LIVE_STORAGE_AND_COST_GATES_ONLY'
    assert cfg['report_reserved_SU'] == RESERVE and cfg['storage_project'] == 231181 and cfg['mdt'] == 1
    assert cfg['storage_root'] == str(root) and re.fullmatch('[0-9a-f]{64}', cfg['cleanup_audit_sha256'])
    assert cfg['no_mid_path_resume'] and cfg['review_sha256'] == rm['review_sha256']
    assert cfg['max_files_all64_plus_report'] == rm['predicted_new_storage_objects']
    return cfg


def main(a):
    cfg = release(ROOT, a.config_sha256, a.bundle_sha256)
    hist = history(cfg['io_pilot_job'])
    groups = cfg['groups']
    assert len(groups) == 2 and {g['id'] for g in groups} == {'n60-nine-NPG','n60-nine-PI'}
    assert all(g['tasks'] == 32 and g['cpus'] == 1 and g['memory_MiB'] == 2048 for g in groups)
    forecast = sum(g['body_seconds']*32/3600 for g in groups)
    requests = sum(g['wall_minutes']*32/60 for g in groups)
    prior = sum(r['actual_SU'] for r in hist)
    io_requests = 2*5/60
    cap = dict(all_settled_before_recovery_SU=prior, forecast_actual_SU=prior+forecast+RESERVE,
               exposure_SU=prior+requests+RESERVE, historical_requests_SU=BASE_HISTORICAL_REQUESTS+io_requests,
               historical_requests_if_all_submitted_SU=BASE_HISTORICAL_REQUESTS+io_requests+requests+RESERVE,
               actual_cap_SU=CAP_ACTUAL, exposure_cap_SU=CAP_EXPOSURE,
               reserved_report_SU=RESERVE, historical_allocation_rows=hist)
    assert cap['forecast_actual_SU'] <= CAP_ACTUAL and cap['exposure_SU'] <= CAP_EXPOSURE
    if a.stage in ('preflight','formal'):
        assert not any(ROOT.glob('x12-rec-v5-*-BEGIN.json'))
        queue()
        cap['balance_snapshot'] = balance(requests+RESERVE)
        files, total = cfg['max_files_all64_plus_report'], cfg['forecast_physical_bytes_including_reuse_reserve']
        q = quota(ROOT, files, total)
        if a.stage == 'preflight':
            print(json.dumps(dict(status='LIVE_STORAGE_COST_ADMISSION_PASS', quota=q, accounting=cap)))
            return
        ids = []
        for g in groups:
            queue(ids)
            # Charge the full joint reservation in both checks. A second array
            # cannot borrow the first array's headroom while it starts writing.
            q = quota(ROOT, files, total)
            row = submit(ROOT, g['algorithm'].lower(), g['wall_minutes'], q, cap, 'formal', g['id'])
            ids.append(row['job'])
        write(ROOT/'RECOVERY_FORMAL_SUBMITTED_v5.json', dict(jobs=ids, accounting=cap, global_concurrency=64))
    else:
        d = read(ROOT/'RECOVERY_FORMAL_SUBMITTED_v5.json')
        assert len(d['jobs']) == 2
        rec = [r for j in d['jobs'] for r in rows(j)]
        assert len(rec) == 64 and all(r['state'] == 'COMPLETED' and r['exitcode'] == '0:0' for r in rec)
        for group in groups:
            for i in range(32):
                key=f"{group['id']}-task-{i:02d}"
                assert (ROOT/f'{key}.tar').is_file()
                tail=(ROOT/f'{key}.jsonl').read_bytes().splitlines()[-1]
                p=json.loads(tail)
                assert p['kind']=='TASK_FINAL' and p['status']=='COMPLETE' and p['config_sha256']==a.config_sha256
        prior += sum(r['actual_SU'] for r in rec)
        assert prior + RESERVE <= min(CAP_EXPOSURE, CAP_ACTUAL)
        queue()
        q = quota(ROOT, 20, 256*1024**2)
        report = dict(prior_actual_SU=prior, requested_upper_SU=RESERVE, exposure_SU=prior+RESERVE,
                      report_new_training_transitions=0, prior_rows=hist+rec, balance_snapshot=balance(RESERVE),
                      historical_requests_including_report_SU=cap['historical_requests_if_all_submitted_SU'])
        submit(ROOT, 'report', RESERVE*60, q, report, 'report')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--bundle-sha256', required=True)
    parser.add_argument('stage', choices=('preflight','formal','report'))
    main(parser.parse_args())
