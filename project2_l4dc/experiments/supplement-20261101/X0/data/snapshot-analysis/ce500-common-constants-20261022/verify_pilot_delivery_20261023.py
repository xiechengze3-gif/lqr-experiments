"""Verify delivery hashes and independently aggregate the saved pilot rows."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import tarfile


root = Path(__file__).resolve().parent
archive = root / 'pilot-20261023.tar.gz'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(archive) == '12b94556df6d3e6aa2574f7750ce1c83d0dd6b6c198f1d77b956324eb44a2cf6'
with tarfile.open(archive, 'r:gz') as tf:
    members = tf.getmembers()
    for member in members:
        target = (root / member.name).resolve()
        assert target.is_relative_to(root) and member.isfile()
        if target.exists():
            assert target.read_bytes() == tf.extractfile(member).read(), member.name
    tf.extractall(root)

read = lambda p: json.loads(p.read_text(encoding='utf-8'))
manifest = read(root / 'pilot_delivery_manifest_20261023.json')
assert all(sha(root / name) == value for name, value in manifest['files'].items())
cfg = read(root / 'resolved_config.json')
report = read(root / 'report-pilot/summary.json')
audit = read(root / 'audit-shards/pilot-00.json')
assert report['seeds'] == cfg['pilot_seeds'] == [700, 701]
assert audit['status'] == 'PASS' and audit['identity'] == report['identity']
assert audit['unique_policies'] == report['unique_policies_audited'] == 198
assert audit['OLS_fits'] == report['OLS_fits_audited'] == 10
assert audit['full_rank_identity_checks'] == 22
grid = [n + cfg['burn'] for n in cfg['budgets']]
recomputed = {}
for rank in cfg['ranks']:
    raw = [read(root / 'raw' / f'ce-r{rank:03d}-s{s:04d}.json') for s in report['seeds']]
    for data in raw:
        assert data['identity'] == report['identity'] and data['physical_transitions'] == grid[-1]
        assert len(data['records']) == 22
        for row in data['records']:
            assert row['transitions'] == row['ols_samples'] + cfg['burn']
        for budget in cfg['budgets']:
            pair = [row for row in data['records'] if row['ols_samples'] == budget]
            assert [r['method'] for r in pair] == ['dense', 'truncated']
            assert pair[0]['policy_sha256'] == pair[1]['policy_sha256']
            if rank == cfg['n']:
                assert {k: v for k, v in pair[0].items() if k != 'method'} == {k: v for k, v in pair[1].items() if k != 'method'}
    for method in ['dense', 'truncated']:
        for epsilon in cfg['absolute_targets']:
            successes = []
            for budget in cfg['budgets']:
                rows = [next(r for r in data['records'] if r['method'] == method and r['ols_samples'] == budget) for data in raw]
                successes.append(sum(r['stable'] and r['gap'] <= epsilon for r in rows))
            hits = [i for i, x in enumerate(successes) if x / len(raw) >= cfg['required_success_fraction']]
            sustained = [i for i in hits if all(x / len(raw) >= cfg['required_success_fraction'] for x in successes[i:])]
            expected = grid[sustained[0]] if sustained else None
            saved = next(r for r in report['requirements'] if r['rank'] == rank and r['method'] == method and r['absolute_target'] == epsilon)
            assert saved['N_hat_90'] == (grid[hits[0]] if hits else None)
            assert saved['sustained_N90'] == expected and saved['endpoint_successes'] == successes[-1]
            recomputed[rank, method, epsilon] = expected
            scaled = next(r for r in report['normalized_sample_complexity'] if r['rank'] == rank and r['method'] == method and r['absolute_target'] == epsilon)
            assert scaled['sample_count'] == expected
            assert scaled['epsilon_N_over_r_d'] == (epsilon * expected / (rank * 2 * cfg['n']) if expected else None)
    for gain in [r for r in report['same_accuracy_gains'] if r['rank'] == rank]:
        nd, nt = [recomputed[rank, m, gain['absolute_target']] for m in ['dense', 'truncated']]
        assert gain['dense_samples'] == nd and gain['truncated_samples'] == nt
        assert gain['sample_gain'] == (nd / nt if nd and nt else None)
        assert gain['gain_lower_bound'] == (grid[-1] / nt if nd is None and nt else None)
assert report['physical_transitions'] == len(cfg['ranks']) * len(report['seeds']) * grid[-1]
receipt = read(root / 'submission-formal.json')
assert len(receipt['jobs']) == 7 and receipt['status'] == 'submitted' and 'pending_submission' not in receipt
assert receipt['plan']['numerical_identity'] == report['identity']
assert receipt['plan']['seeds'] == list(range(800, 830)) and receipt['plan']['budgets'] == cfg['budgets']
assert receipt['plan']['total_worst_case_SU_bound'] < 100
state = read(root / 'formal_submission_verification_20261023.json')
assert state['status'] == 'PASS'
output = dict(status='PASS', checked_at_utc=datetime.now(timezone.utc).isoformat(),
              files=len(manifest['files']), saved_policy_rows=220, unique_policies_independently_audited=198,
              independently_reaggregated_targets=40, full_rank_identity_checks=22,
              primary_pilot_same_accuracy_gains=[r for r in report['same_accuracy_gains'] if r['absolute_target'] == .1],
              rank_scaling_observation='Truncated pilot samples are not proportional to rank; normalized coefficients are not flat.',
              formal_status_at_remote_snapshot='20 running, 130 pending, six audit shards and report dependent',
              formal_jobs=receipt['jobs'], total_worst_case_SU_bound=receipt['plan']['total_worst_case_SU_bound'])
(root / 'pilot_delivery_verification_20261023.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(output, ensure_ascii=False, indent=2))
