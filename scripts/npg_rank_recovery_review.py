"""Read-only recheck of frozen runs; corrected review artifacts on Grace."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path


def main(root, manifest, destination):
    root, manifest, out = Path(root), Path(manifest), Path(destination)
    config = json.loads(manifest.read_text())
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    endpoints, checked = [], 0
    thresholds = {(int(r['task_id']), r['method'], float(r['epsilon'])): r
                  for r in csv.DictReader((root/'report/thresholds_per_run.csv').open())}
    reference = json.loads((root/'reference.json').read_text())
    assert reference['manifest_sha256'] == manifest_hash
    exact = {(r['n'], r['r'], r['system_seed']): r['gap']
             for r in reference['records']
             if r['stage'] == config['stages'] and not r['finite_horizon']}
    for tid, task in enumerate(config['tasks']):
        payload = json.loads((root/'raw'/f'task-{tid:03d}.json').read_text())
        assert payload['task'] == task and payload['manifest_sha256'] == manifest_hash
        for method in ('raw', 'truncated'):
            rows = sorted((r for r in payload['records'] if r['method'] == method), key=lambda r: r['stage'])
            assert [r['stage'] for r in rows] == list(range(config['stages']+1))
            total = 0
            for i, row in enumerate(rows):
                if i:
                    total += config['burn'] + (config['batch_schedule'][i-1]+1)*config['horizon']
                assert row['transitions'] == total
                assert row['stable'] and row['gap'] is not None
            for eps in config['tolerances']:
                good = [r['stable'] and r['gap'] <= eps for r in rows]
                first = next((i for i in range(len(rows)) if good[i]), None)
                window = config['threshold_window']
                confirmed = next((i+window-1 for i in range(len(rows)-window+1)
                                  if all(good[i:i+window])), None)
                sustained = next((i+window-1 for i in range(len(rows)-window+1)
                                  if all(good[i:])), None)
                recorded = thresholds[tid, method, eps]
                for name, index in [('first_hit', first), ('confirmed_window', confirmed), ('sustained', sustained)]:
                    value = int(recorded[name]) if recorded[name] else None
                    assert value == (rows[index]['transitions'] if index is not None else None)
                checked += 1
            last = rows[-1]
            endpoints.append(dict(n=task['n'], r=task['r'], system_seed=task['system_seed'],
                                  method=method, gap=last['gap'], transitions=last['transitions'],
                                  exact_gap=exact[task['n'], task['r'], task['system_seed']]))
    diagnostic = json.loads((root/'report/endpoint_diagnostic.json').read_text())
    groups = []
    for original in diagnostic['records']:
        subset = [r for r in endpoints if (r['n'], r['r'], r['method']) ==
                  (original['n'], original['r'], original['method'])]
        gap = sum(r['gap'] for r in subset)/len(subset)
        exact_gap = sum(r['exact_gap'] for r in subset)/len(subset)
        excess = gap-exact_gap
        assert abs(gap-original['gap_mean']) < 1e-10
        assert abs(excess-original['sample_minus_exact_mean']) < 1e-10
        normalized = excess/(original['r']*original['n']**2)
        assert abs(normalized-original['normalized_excess_rn2']) < 1e-12
        groups.append(dict(n=original['n'], r=original['r'], method=original['method'],
                           gap=gap, exact_gap=exact_gap, normalized_excess=normalized))
    out.mkdir(parents=True, exist_ok=True)
    audit = dict(status='PASS', configurations=len(config['tasks']), stable_methods=len(endpoints),
                 checked_threshold_rows=checked, manifest_sha256=manifest_hash,
                 review_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 endpoint_json_matches_raw=True, full_budget=endpoints[0]['transitions'], endpoints=groups)
    (out/'recovery_audit.json').write_text(json.dumps(audit, indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, n in zip(axes, (50, 100)):
        for method, color, style in [('raw', '#777777', '--'), ('truncated', '#12699c', '-')]:
            selected = sorted((r for r in groups if r['n'] == n and r['method'] == method), key=lambda r: r['r'])
            ax.plot([r['r'] for r in selected], [r['gap'] for r in selected], 'o'+style, color=color, label=method)
        selected = sorted((r for r in groups if r['n'] == n and r['method'] == 'raw'), key=lambda r: r['r'])
        ax.plot([r['r'] for r in selected], [r['exact_gap'] for r in selected], 'o-', color='#269b62', label='exact critic (diagnostic)')
        ax.set_xscale('log', base=2)
        ax.set_xticks([1,2,4,8,16], labels=[1,2,4,8,16])
        ax.set_title(f'n = {n}')
        ax.set_xlabel('Rank r'); ax.set_ylabel('Final absolute cost gap')
        ax.grid(alpha=.2); ax.legend(fontsize=8)
    fig.suptitle('Frozen NPG rank sweep: endpoint means of two systems\n80 updates; 656,491,776 primitive transitions per sampled method')
    fig.tight_layout(rect=(0,0,1,.89))
    for ext in ('png','pdf'):
        fig.savefig(out/f'review_endpoint.{ext}', dpi=180, bbox_inches='tight')
    plt.close(fig)
    print(json.dumps({k:v for k,v in audit.items() if k != 'endpoints'}), flush=True)


if __name__ == '__main__':
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Numerical reporting requires Grace Slurm compute nodes')
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True); parser.add_argument('--manifest', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    main(args.root, args.manifest, args.destination)
