"""Freeze a common fine CE prefix grid; packaging only, no local simulation."""
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = Path('E:/ChatGPT/Results/LQR_experiments')


def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    previous = read(ROOT/'configs/ce_high_rank_20261015.json')
    old = RESULTS/'grace-ce-high-rank-fb68e24f9cb40c74/results/ce-high-rank-fb68e24f9cb40c74'
    inputs = [(Path(d['source']), d['task']) for d in previous['reused']]
    inputs += [(old/'raw'/f'task-{i:03d}.json', t) for i, t in enumerate(previous['new_tasks'])]
    datasets = [dict(task=t, source=str(p), sha256=sha(p), bundle_path=f"historical/r{t['r']}-s{t['system_seed']}.json")
                for p, t in sorted(inputs, key=lambda item: (item[1]['r'], item[1]['system_seed']))]
    assert len(datasets) == 8
    # Every inserted prefix ends on the historical 1024-transition collector boundary.
    # Retain the initial partial chunks (512 then 2048), preserving random draws.
    budgets = sorted(set([512, 2048, 8192] + list(range(32768, 262145, 2048)) + list(range(266240, 524289, 4096))))
    files = ['dense_scaling.py', 'scripts/ce_high_rank.py', 'scripts/ce_precision_zoom.py',
             'scripts/prepare_ce_precision_zoom.py', 'slurm/ce_precision_zoom.sbatch']
    cfg = dict(title='100d CE fixed absolute precision .1, fine common prefixes', n=100,
               ranks=[16, 32, 64, 100], system_seeds=[0, 1], sampling_seed=0,
               absolute_epsilon=.1, burn=512, sigma=1., budgets=budgets, datasets=datasets,
               methods=['raw', 'truncated'], previous_release=previous['release'],
               criterion='All two systems stable with J-Jstar <= .1 at a common fixed prefix; also report each seed and sustained attainment',
               reuse='Historical endpoints frozen; sufficient statistics absent, so replay eight streams to obtain missing prefixes. Shared historical prefixes must reproduce.',
               new_physical_transitions=8*(max(budgets)+512),
               resources=dict(cores=1, threads=1, memory_GiB=2, wall_minutes=5,
                              array_elements=8, production_concurrency=2, report_elements=1,
                              maximum_reserved_SU=.75, campaign_SU_ceiling=1., automatic_retries=0,
                              expected_SU_range=[.15, .65],
                              performance_basis='Previous n100 collector/7-prefix fits 26-30 seconds. More DARE evaluations now; strict five-minute cap per element.'),
               sources={f: sha(ROOT/f) for f in files})
    release = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]
    cfg['release'] = release
    config = ROOT/'configs/ce_precision_zoom.json'
    config.write_text(json.dumps(cfg, indent=2)+'\n')
    bundle = ROOT/'analysis/ce-precision-zoom/release'/release
    bundle.mkdir(parents=True, exist_ok=True)
    for f in files:
        dest = bundle/f
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/f, dest)
    for d in datasets:
        dest = bundle/d['bundle_path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(d['source'], dest)
        assert sha(dest) == d['sha256']
    shutil.copy2(config, bundle/'manifest.json')
    (bundle/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(bundle).as_posix()}\n'
        for p in sorted(bundle.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS'), newline='\n')
    archive = ROOT/'packages'/f'ce-precision-zoom-{release}.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for p in sorted(bundle.rglob('*')):
            if p.is_file(): tar.add(p, arcname=p.relative_to(bundle).as_posix())
    receipt = dict(state='PREPARED', release=release, archive=str(archive), archive_sha256=sha(archive),
                   prefix_count=len(budgets), new_physical_transitions=cfg['new_physical_transitions'],
                   maximum_reserved_SU=.75, campaign_SU_ceiling=1.)
    (ROOT/'receipts/ce-precision-zoom.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt))


if __name__ == '__main__': main()
