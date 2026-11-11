"""Package adaptive CE extension; local standard-library operations only."""
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    previous = read(ROOT/'configs/ce_precision_zoom.json')
    receipt = read(ROOT/'receipts/ce-precision-zoom.json')
    assert receipt['state'] == 'COMPLETE_RETRIEVED_SHA256_VERIFIED'
    datasets = []
    for index, item in enumerate(previous['datasets']):
        p = Path(receipt['result_directory'])/'raw'/f'task-{index:03d}.json'
        assert read(p)['task'] == item['task']
        datasets.append(dict(task=item['task'], source=str(p), sha256=sha(p), bundle_path=f'historical/task-{index:03d}.json'))
    files = ['dense_scaling.py', 'scripts/ce_high_rank.py', 'scripts/adaptive_rank.py',
             'scripts/ce_precision_zoom.py', 'scripts/ce_adaptive_zoom.py',
             'scripts/prepare_ce_adaptive_zoom.py', 'slurm/ce_adaptive_zoom.sbatch']
    cfg = dict(title='Adaptive unknown-rank CE at fixed absolute precision .1', n=100,
        ranks=previous['ranks'], system_seeds=[0, 1], sampling_seed=0,
        budgets=previous['budgets'], burn=512, sigma=1., absolute_epsilon=.1,
        datasets=datasets, methods=['raw', 'truncated', 'adaptive'],
        adaptive=dict(method='adaptive_1', multiplier=1.,
            scale='operator_norm(B_OLS_first_half-B_OLS_second_half)/2',
            split='contiguous equal halves of the same prefix; full original-coordinate OLS unchanged',
            forbidden_inputs=['true rank', 'true B', 'optimal cost', 'test gap']),
        previous_release=previous['release'],
        new_physical_transitions=8*(max(previous['budgets'])+512),
        criterion='All two systems stable with absolute J-Jstar <= .1 at fixed prefixes; report first and sustained attainment',
        resources=dict(cores=1, threads=1, memory_GiB=2, wall_minutes=5, production_concurrency=2,
            verify_elements=1, array_elements=8, report_elements=1, automatic_retries=0,
            maximum_reserved_SU=10*5/60, campaign_SU_ceiling=1., expected_SU_range=[.15, .5],
            basis='Previous 8-stream 180-prefix CE replay plus report used 436 single-core elapsed seconds; one extra DARE and two half-statistic solves per prefix.'),
        sources={f: sha(ROOT/f) for f in files})
    release = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]
    cfg['release'] = release
    config = ROOT/'configs/ce_adaptive_zoom.json'
    config.write_text(json.dumps(cfg, indent=2)+'\n')
    bundle = ROOT/'analysis/ce-adaptive-zoom/release'/release
    bundle.mkdir(parents=True, exist_ok=True)
    for f in files:
        dest = bundle/f
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/f, dest)
    for item in datasets:
        dest = bundle/item['bundle_path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item['source'], dest)
        assert sha(dest) == item['sha256']
    shutil.copy2(config, bundle/'manifest.json')
    (bundle/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(bundle).as_posix()}\n'
        for p in sorted(bundle.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS'), newline='\n')
    archive = ROOT/'packages'/f'ce-adaptive-zoom-{release}.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for p in sorted(bundle.rglob('*')):
            if p.is_file(): tar.add(p, arcname=p.relative_to(bundle).as_posix())
    value = dict(state='PREPARED', release=release, archive=str(archive), archive_sha256=sha(archive),
        prefix_count=len(cfg['budgets']), new_physical_transitions=cfg['new_physical_transitions'],
        maximum_reserved_SU=cfg['resources']['maximum_reserved_SU'], campaign_SU_ceiling=1.)
    (ROOT/'receipts/ce-adaptive-zoom.json').write_text(json.dumps(value, indent=2)+'\n')
    print(json.dumps(value))

if __name__ == '__main__': main()
