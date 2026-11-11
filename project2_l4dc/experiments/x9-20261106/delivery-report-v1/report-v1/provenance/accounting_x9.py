"""Own-X9 accounting snapshots only; Slurm elapsed and AMS settlement overlap."""
import datetime
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

OUT = Path('/scratch/user/changze/lqr_experiments/results/x9-20261106')
ACCOUNT = '132685389143'


def main():
    ledger = json.loads((OUT/'budget/ledger.json').read_text())
    assert ledger['study'] == 'X9' and ledger['cap_requested_SU'] == 50
    own = {str(r['job']) for r in ledger['submissions'] if r.get('job')}
    assert own
    raw = subprocess.check_output(['sacct', '--array', '-j', ','.join(sorted(own)), '-n', '-P',
           '--format=JobID%48,JobIDRaw,State%40,ElapsedRaw,AllocCPUS,MaxRSS,AllocTRES'], universal_newlines=True)
    allocations, steps, unknown = [], [], []
    physical = set()
    for line in raw.splitlines():
        if not line.strip():
            continue
        fields = line.split('|')
        job, ident, state, elapsed, cpus, rss, tres = [x.strip() for x in fields[:7]]
        assert job.split('_')[0].split('.')[0] in own
        physical.add(ident.split('.')[0])
        row = dict(job=job, physical_job_id=ident, state=state,
                   elapsed_seconds=int(elapsed), cpus=int(cpus), max_RSS=rss, allocated_TRES=tres)
        if '.' in job:
            steps.append(row)
            continue
        parsed = dict(p.split('=', 1) for p in tres.split(',') if '=' in p)
        if int(elapsed) == 0:
            row['elapsed_billing_SU'] = 0.
        elif 'billing' in parsed:
            row['billing_cores'] = float(parsed['billing'])
            row['elapsed_billing_SU'] = int(elapsed)*float(parsed['billing'])/3600
        else:
            row['elapsed_billing_SU'] = None
            unknown.append(job)
        allocations.append(row)
    end = (datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    process = subprocess.Popen(['myproject', '-j', ACCOUNT, '-s', '2026-11-05', '-e', end],
                               stdout=subprocess.PIPE, universal_newlines=True)
    settled, unparsed, seen = [], [], set()
    for line in process.stdout:
        tokens = re.findall(r'(?<!\d)\d{8}(?:_\d+)?(?!\d)', line)
        if not any(token in own or token in physical or token.split('_')[0] in own for token in tokens):
            continue
        cells = [v.strip() for v in line.split('|')]
        try:
            assert cells[1] == ACCOUNT
            identity = (cells[2], cells[3])
            assert identity not in seen
            seen.add(identity)
            settled.append(dict(job=cells[2], array_index=cells[3],
                                elapsed_seconds=int(cells[7]), slots=float(cells[8]),
                                displayed_rounded_SU=float(cells[9])))
        except (IndexError, ValueError, AssertionError):
            unparsed.append(line.rstrip())
    assert process.wait() == 0
    account = subprocess.check_output(['myproject'], universal_newlines=True)
    summary = next(line for line in account.splitlines() if '|'+ACCOUNT+'|' in line)
    result = dict(status='OWN_X9_ACCOUNTING_VERIFIED' if not unknown and not unparsed else 'OWN_ACCOUNTING_NEEDS_REVIEW',
                  checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  cap_requested_SU=50, cumulative_requested_SU=ledger['cumulative_requested_SU'],
                  Slurm_elapsed_billing_SU=None if unknown else sum(r['elapsed_billing_SU'] for r in allocations),
                  AMS_settled_walltime_slots_SU=sum(r['elapsed_seconds']*r['slots']/3600 for r in settled),
                  AMS_displayed_rounded_SU_sum=sum(r['displayed_rounded_SU'] for r in settled),
                  AMS_own_settled_rows=len(settled), Slurm_allocation_rows=len(allocations),
                  allocations=allocations, steps=steps, settled_records=settled,
                  unknown_Slurm_billing_jobs=unknown, unparsed_own_AMS_rows=unparsed,
                  account_summary_line=summary,
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  note='Slurm and AMS are overlapping views, never added. Used & Pending includes reservations; current account balance is not X9 spend. Only own-X9 records retained.')
    assert result['cumulative_requested_SU'] <= 50
    target = OUT/'budget'/('accounting-'+str(time.time_ns())+'.json')
    result['snapshot_path'] = str(target)
    with target.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ['allocations', 'steps', 'settled_records']}), flush=True)


if __name__ == '__main__':
    main()
