"""Aggregate saved rows only; no new plant, trajectory or controller simulation."""
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics


root = Path(__file__).resolve().parent
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
cfg = read(root / 'resolved_config.json')
rows = []
for rank in cfg['ranks']:
    data = [read(root / 'raw' / f'ce-r{rank:03d}-s{s:04d}.json') for s in cfg['pilot_seeds']]
    for n in [65536, 131072, 262144, 1048576, 2097152]:
        pair = {m: [next(r for r in d['records'] if r['ols_samples'] == n and r['method'] == m) for d in data] for m in ['dense', 'truncated']}
        tg = [r['gap'] for r in pair['truncated']]
        rows.append(dict(rank=rank, ols_samples=n, primitive_transitions=n+cfg['burn'],
                         pilot_seeds=cfg['pilot_seeds'], dense_gaps=[r['gap'] for r in pair['dense']], truncated_gaps=tg,
                         dense_B_fro2_median=statistics.median(r['B_error_fro2'] for r in pair['dense']),
                         truncated_B_fro2_median=statistics.median(r['B_error_fro2'] for r in pair['truncated']),
                         A_fro2_median=statistics.median(r['A_error_fro2'] for r in pair['dense']),
                         truncated_N_times_gap_median=n*statistics.median(tg)))

# Read-only Grace query performed this turn, before loss of shared connection.
# These are observed scalar rows, not a downloaded full raw-file audit.
formal_first = dict(ols_samples=131072, primitive_transitions=131328, seed=800,
    truncated_gaps={'2': .14785575453754518, '4': .12847453657832375, '8': .14877522764709283,
                    '32': .0984183298141943, '500': .20781110294808514},
    source='Grace read-only query of raw/ce-r*-s0800.json on 2026-10-23 about 19:42 UTC',
    full_files_downloaded=False, independent_policy_audit_for_these_rows='not yet downloaded/completed')

output = dict(status='PASS_saved_rows_reaggregated', timestamp_utc=datetime.now(timezone.utc).isoformat(),
    pilot_rows=rows, formal_seed800_observation=formal_first,
    findings=[
        'The pilot 90% rule with two seeds requires both seeds to pass.',
        'At N=131072, pilot seed701 has rank2 gap below rank8 gap; seed700 determines the crossing reversal.',
        'Formal seed800 rank8 fails epsilon=.1 at N=131072, so the pilot rank8 crossing has not persisted across all new seeds.',
        'At the largest N, truncated N*median(gap) is about 10-12.5k for ranks2/4/8/32, rather than proportional to rank.',
        'The common certificate bounds do not equalize stationary excitation or local Riccati sensitivity.',
    ],
    geometric_dimension_comparison=[dict(rank=r, dense_B_parameters=250000,
        rank_r_tangent_dimension=r*(1000-r), isotropic_B_noise_dimension_ratio=250000/(r*(1000-r))) for r in [70,150,300]],
    dimension_comparison_scope='Tangent-space Frobenius noise under isotropic entry noise; not a control-gap or sample-gain prediction.',
    new_rank_extension_status='frozen locally; not uploaded or submitted because existing Grace session became unavailable',
    new_rank_mechanism_diagnostic_status='implemented and frozen; not executed')
(root/'rank_reversal_analysis_20261023.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(status=output['status'], at_131072=[r for r in rows if r['ols_samples']==131072],
    at_2097152=[{'rank':r['rank'],'N_gap':r['truncated_N_times_gap_median']} for r in rows if r['ols_samples']==2097152],
    formal_first=formal_first), ensure_ascii=False, indent=2))
