"""Freeze a missing-cell-only Grace release, using standard library file I/O."""
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = Path('E:/ChatGPT/Results/LQR_experiments/final-round-20261014')
DEST = ROOT/'analysis/alignment-20261015'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    pi = read(ROOT/'configs/final_round_20261014.json')
    npg = read(ROOT/'configs/npg_rank_scaling.json')
    ce = read(ROOT/'configs/cross_rank_ce.json')
    for name, digest in pi['sources'].items():
        if sha(ROOT/name) != digest:
            raise ValueError('Historical PI source changed: '+name)
    tasks, reuse = [], []
    for n in (50, 100):
        for rank in (1, 2, 4, 8, 16, 32):
            for seed in pi['system_seeds']:
                for blocks in pi['blocks_per_update']:
                    if (n, rank) == (50, 4):
                        for method in pi['methods']:
                            source = OLD/'core'/f'n50-r4-s{seed}-d0-b{blocks}-{method}.json'
                            data = read(source)
                            assert data['meta']['config_sha256'] == sha(OLD/'frozen_config.json')
                            assert data['meta']['updates'] == 8 and data['meta']['eta'] == .25
                            assert data['meta']['actual_transitions'] == 8*(512+(blocks+1)*16)
                            assert data['meta']['status'] == 'completed'
                            reuse.append(dict(algorithm='Direct_Stein_PI', n=n, r=rank,
                                              system_seed=seed, blocks=blocks, method=method,
                                              path=str(source), sha256=sha(source)))
                        continue
                    tasks.append(dict(algorithm='Direct_Stein_PI', n=n, r=rank, system_seed=seed,
                                      sampling_seed=0, blocks=blocks, methods=pi['methods'],
                                      updates=8, eta=.25,
                                      planned_transitions=3*8*(512+(blocks+1)*16)))
    for algorithm, cfg in [('CE', ce), ('NPG', npg)]:
        for n in (50, 100):
            for seed in (0, 1):
                task = dict(algorithm=algorithm, n=n, r=32, system_seed=seed,
                            sampling_seed=0, methods=['dense', 'known_rank'])
                task['planned_transitions'] = (max(ce['budgets'])+512 if algorithm == 'CE' else
                                               2*sum(1024+(b+1)*16 for b in npg['batch_schedule']))
                tasks.append(task)
    for index, task in enumerate(tasks):
        task['id'] = index
    config = dict(title='Rank/dimension extension with historical-data reuse', date='2026-10-15',
                  dimensions=[50, 100], ranks=[1, 2, 4, 8, 16, 32], primary_target=.1,
                  target_definition='(J(K)-Jstar)/(J(K0)-Jstar) <= .1',
                  primary_output='PI fixed stage 8; NPG fixed stage 80; CE fixed declared data prefix',
                  system_family='dense_scaling.system coupled_unstable isotropic 981113; A varies with rank',
                  pi=dict(system_seeds=pi['system_seeds'], sampling_seeds=[0], methods=pi['methods'],
                          blocks_per_update=pi['blocks_per_update'], eta=.25, updates=8,
                          burn=512, horizon=16, sigma=1., threshold_multiplier=1., joint_block_weights=[1., 1.]),
                  npg=dict(system_seeds=[0, 1], methods=['dense', 'known_rank'],
                           batch_schedule=npg['batch_schedule'], burn=1024, horizon=16,
                           sigma=1., step_multiplier=npg['step_multiplier']),
                  ce=dict(system_seeds=[0, 1], methods=['dense', 'known_rank'],
                          budgets=ce['budgets'], burn_actual=512, sigma=1.),
                  tasks=tasks, reused_pi=reuse,
                  planned_new_transitions=sum(t['planned_transitions'] for t in tasks),
                  new_pi_trajectories=sum(len(t['methods']) for t in tasks if t['algorithm']=='Direct_Stein_PI'),
                  new_npg_trajectories=8, new_ce_shared_prefix_datasets=4,
                  budget=dict(production_SU_ceiling=200., benchmark_SU_ceiling=2.,
                              report_SU_ceiling=1., automatic_retries=0,
                              production_requires='Grace verification PASS, measured full-path runtime/RSS, current allocation and queue, a reviewed per-task reservation plan within the whole-campaign ceiling'),
                  comparison='Within-method rank gains; CE/NPG seed0/1 reuse, PI seed101..108 reuse. Same generator and criterion, but different seed cohorts and schedules: no paired cross-algorithm claim.',
                  known_gaps='Adaptive NPG only available at n100 r1..16; CE adaptive absent in this historical cohort. Do not imply three-arm coverage for CE or NPG.',
                  state='PREPARED_NOT_SUBMITTED')
    files = ['dense_scaling.py', 'requirements.txt', 'scripts/npg_batched_collector.py',
             'scripts/direct_stein_final.py', 'scripts/final_round.py', 'scripts/final_npg_audit.py',
             'scripts/adaptive_rank.py', 'scripts/adaptive_rank_run.py', 'scripts/full_lstd.py',
             'scripts/npg_precision_audit.py', 'scripts/test_direct_stein_final.py',
             'scripts/test_final_failure_paths.py', 'scripts/aligned_extension.py',
             'slurm/aligned_extension.sbatch', 'scripts/prepare_aligned_extension.py',
             'docs/ALIGNED_EXTENSION_PROTOCOL_20261015.md']
    hashes = {name: sha(ROOT/name) for name in files}
    config['sources'] = hashes
    payload = json.dumps(config, sort_keys=True).encode()
    release = hashlib.sha256(payload).hexdigest()[:16]
    config['release'] = release
    config_path = ROOT/'configs/aligned_extension_20261015.json'
    config_path.write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
    bundle = DEST/'release'/release
    bundle.mkdir(parents=True, exist_ok=True)
    for name in files:
        dest = bundle/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/name, dest)
    reused_hashes = {}
    for item in reuse:
        source = Path(item['path'])
        target = bundle/'reused_pi'/source.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(source, target)
        shutil.copy2(source.with_suffix('.npz'), target.with_suffix('.npz'))
        for path in (target, target.with_suffix('.npz')):
            reused_hashes[path.relative_to(bundle).as_posix()] = sha(path)
    fixtures = []
    old_npg = Path('E:/ChatGPT/Results/LQR_experiments/npg-rank-complete-ea112fabeef4eb4a/npg-rank-ea112fabeef4eb4a/raw')
    for path in sorted(old_npg.glob('task-*.json')):
        data = read(path)
        if (data['task']['n'], data['task']['r'], data['task']['system_seed']) in [(50, 4, 0), (100, 4, 0)]:
            fixtures.append(dict(algorithm='NPG', task=data['task'], initial_gap=data['diagnostics']['initial_gap'],
                                 rows=[r for r in data['records'] if r['stage'] <= 1],
                                 source_sha256=sha(path), engine_sha256=data['engine_sha256']))
    for n, rank, seed in [(50, 4, 101)]:
        for method in pi['methods']:
            data = read(OLD/'core'/f'n{n}-r{rank}-s{seed}-d0-b32768-{method}.json')
            fixtures.append(dict(algorithm='Direct_Stein_PI', task=data['meta'], initial_gap=data['initial_gap'], rows=data['rows'][:2]))
    old_ce = Path('E:/ChatGPT/Results/LQR_experiments/cross-rank-complete-709f81b14811afb5/cross-rank-709f81b14811afb5/ce/raw')
    for path in sorted(old_ce.glob('task-*.json')):
        data = read(path)
        if (data['task']['n'], data['task']['r'], data['task']['system_seed'], data['task']['tail']) in [(50, 4, 0, 0.), (100, 4, 0, 0.)]:
            rows = [r for r in data['records'] if r['N'] == min(ce['budgets'])]
            fixtures.append(dict(algorithm='CE', task=data['task'], initial_gap=rows[0]['gap']/rows[0]['relative_gap'],
                                 rows=rows, source_sha256=sha(path), engine_sha256=data['engine_sha256']))
    (bundle/'fixtures.json').write_text(json.dumps(fixtures, indent=2)+'\n', encoding='utf-8')
    shutil.copy2(config_path, bundle/'manifest.json')
    all_hashes = dict(hashes, **{'manifest.json': sha(bundle/'manifest.json'), 'fixtures.json': sha(bundle/'fixtures.json')})
    all_hashes.update(reused_hashes)
    (bundle/'SHA256SUMS').write_text(''.join(f'{h}  {name}\n' for name, h in all_hashes.items()), encoding='utf-8', newline='\n')
    archive = ROOT/'packages'/f'aligned-extension-{release}.tar.gz'
    with tarfile.open(archive, 'w:gz') as handle:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                handle.add(path, arcname=str(path.relative_to(bundle)).replace('\\', '/'))
    receipt = dict(state='PREPARED_NOT_SUBMITTED', release=release, archive=str(archive), archive_sha256=sha(archive),
                   tasks=len(tasks), reused_pi_trajectories=len(reuse),
                   new_pi_trajectories=config['new_pi_trajectories'], new_npg_trajectories=8,
                   new_ce_datasets=4, planned_new_transitions=config['planned_new_transitions'],
                   benchmark_SU_ceiling=2, production_SU_ceiling=200,
                   blocker='No shared Grace connection; allocation and measured remote runtime not yet available.')
    (ROOT/'receipts/aligned-extension-20261015.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
