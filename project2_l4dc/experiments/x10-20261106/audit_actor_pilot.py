"""Read-only X10b pilot/resource audit. Standard library, no outcome selection."""
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

BASE = Path('/scratch/user/changze/lqr_experiments')
OUT = BASE/'results/x10-20261106/X10b'
RELEASE = BASE/'releases/x10-20261106-b-pilot-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slurm(job):
    raw = subprocess.check_output(['sacct', '-X', '--array', '-j', job, '-n', '-P',
          '--format=JobID,JobIDRaw,State,ElapsedRaw,AllocTRES'], universal_newlines=True)
    rows = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        jid, jid_raw, state, seconds, tres = line.split('|')[:5]
        assert '.' not in jid
        alloc = dict(item.split('=', 1) for item in tres.split(',') if '=' in item)
        billing = int(alloc.get('billing', '0'))
        cpu = int(alloc.get('cpu', '0'))
        rows.append(dict(job=jid, job_raw=jid_raw, state=state,
                         elapsed_seconds=int(seconds), alloc_tres=tres,
                         billing_cores=billing, cpus=cpu))
    return rows


def main():
    cfg_path = RELEASE/'actor-config-protocol-v1.json'
    cfg = json.loads(cfg_path.read_text())
    for name, digest in cfg['scientific_sources'].items():
        assert sha(RELEASE/name) == digest, name
    chain = json.loads((OUT/'submissions/PILOT_CHAIN_v1.json').read_text())
    ledger_path = OUT/'budget/ledger.json'
    ledger = json.loads(ledger_path.read_text())
    assert ledger['study'] == 'X10b'
    assert ledger['actual_forecast_cap_SU'] == 160 and ledger['requested_upper_cap_SU'] == 200
    assert abs(ledger['cumulative_requested_SU']-4-1/6) < 1e-9
    assert len(chain['jobs']) == 3
    roles = {}
    for entry in chain['jobs']:
        role = entry['role']
        directory = OUT/'resource-v1'/role
        assert not (directory/'PILOT_HARD_FAILURE.json').exists(), role
        path = directory/'PILOT_DONE.json'
        receipt = json.loads(path.read_text())
        assert receipt['status'] == 'PASS'
        assert receipt['config_sha256'] == sha(cfg_path)
        assert receipt['source_sha256'] == cfg['scientific_sources']['actor_pilot.py']
        assert receipt['actor_sha256'] == cfg['scientific_sources']['actor_paths.py']
        assert receipt['engine_sha256'] == cfg['scientific_sources']['frozen_engine.py']
        assert receipt['peak_RSS_KiB'] <= .8*2*1024*1024
        assert receipt['formal_observation_transitions'] == 0
        assert receipt['automatic_retries'] == 0 and receipt['no_performance_readout']
        rows = slurm(entry['job'])
        assert len(rows) == 1 and rows[0]['state'] == 'COMPLETED', rows
        assert rows[0]['billing_cores'] == rows[0]['cpus'] == 1
        if role == 'equivalence':
            assert {r['algorithm'] for r in receipt['checks']} == {'NPG', 'PI'}
            assert all(r['status'] == 'PASS_BITWISE_SAVED_RECORDS_ARRAYS_RNG_COUNTS'
                       and r['checked_arrays'] > 0 for r in receipt['checks'])
            assert receipt['validation_replay_not_new_formal_replication']
            for item in receipt['checks']:
                p = directory/(item['algorithm']+'-validation-replay')/'DONE.json'
                assert sha(p) == item['replay_done_sha256']
        else:
            assert role in ['NPG', 'PI'] and receipt['algorithm'] == role
            assert (receipt['n'], receipt['system'], receipt['seed']) == (72, 9102, 9801)
            assert [r['rung'] for r in receipt['rows']] == cfg['rungs']
            assert abs(receipt['body_seconds']-sum(r['seconds'] for r in receipt['rows'])) < 1e-8
            for item in receipt['rows']:
                label = 'r'+str(item['rung']).replace('.', '')
                assert sha(directory/label/'DONE.json') == item['done_sha256']
                schedule = next(r for r in cfg['all_schedules'] if r['n'] == 72 and r['rung'] == item['rung'])
                assert item['primitive_per_arm'] == schedule['primitive_per_arm_per_algorithm']
        roles[role] = dict(receipt=receipt, receipt_sha256=sha(path), slurm=rows)
    assert set(roles) == {'equivalence', 'NPG', 'PI'}
    x9 = BASE/'results/x9-20261106'
    x9ledger = json.loads((x9/'budget/ledger.json').read_text())
    x9jobs = []
    for entry in x9ledger['submissions']:
        assert entry['job'], 'Unreconciled X9 reservation'
        x9jobs.append(dict(stage=entry['stage'], job=entry['job'], rows=slurm(entry['job'])))
    x9complete = (any(r['stage'] == 'REPORT' for r in x9jobs)
                  and all(r['rows'] and all(s['state'] == 'COMPLETED' for s in r['rows']) for r in x9jobs))
    balance = subprocess.check_output(['myproject'], universal_newlines=True)
    account = next(line for line in balance.splitlines() if '|132685389143|' in line)
    snapshot = dict(status='PASS_PILOT_SOURCES_COUNTS_RSS_SLURM',
                    checked_utc=datetime.datetime.utcnow().isoformat()+'Z',
                    config_sha256=sha(cfg_path), pilot_roles=roles,
                    pilot_actual_elapsed_SU=sum(r['slurm'][0]['elapsed_seconds']/3600 for r in roles.values()),
                    pilot_requested_upper_SU=ledger['cumulative_requested_SU'],
                    ledger_sha256=sha(ledger_path), x9_compute_jobs=x9jobs,
                    x9_all_compute_including_report_complete=x9complete,
                    myproject_snapshot=balance, account_balance_SU=float(account.split('|')[6].strip()),
                    formal_numerical_work=0, no_performance_readout=True)
    print(json.dumps(snapshot))


if __name__ == '__main__':
    main()
