"""Freeze configurations and source; no local numerical work."""
import hashlib
import json
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = json.loads((root/'configs/npg_rank_scaling.json').read_text())
tasks = list(base['tasks'])
tasks += [dict(t, tail=tail) for tail in (.01, .1, .3)
          for t in base['tasks'] if t['n'] in (50, 100) and t['r'] == 4]
# All matrices and seeds agree across algorithms. Queue order is immaterial.
common = dict(tasks=tasks, burn=1024, tolerances=[5., 2., 1., .5, .1],
              fit_max_rank_fraction=.2, engine_release=base['engine_release'])
configs = {'ce':dict(common, algorithm='CE',
    budgets=[512,2048,8192,32768,131072,524288,2097152])}
for count in (32768,131072,524288):
    configs[f'pi-{count}'] = dict(common, algorithm='PI-LSTD', stages=6,
        batch_schedule=[count]*6, solver_rtol=1e-8, solver_restart=40, solver_maxiter=10)
for count in (4096,16384,65536,262144,1048576):
    configs[f'npg-{count}'] = dict(base, tasks=tasks, stages=80,
        batch_schedule=[count]*80, profile='Fixed-batch NPG cross-algorithm confirmation')
files = ['scripts/full_lstd.py','scripts/pi_ce_rank.py',
         'scripts/pi_ce_rank_report.py','scripts/prepare_pi_ce_rank.py',
         'scripts/npg_rank_scaling.py','scripts/npg_batched_collector.py',
         'slurm/pi_ce_rank.sbatch','docs/PI_CE_RANK_PROTOCOL.md']
for name, cfg in configs.items():
    path = f'configs/cross_rank_{name}.json'
    (root/path).write_text(json.dumps(cfg, indent=2)+'\n', encoding='utf-8', newline='\n')
    files.append(path)
index = dict(profiles=list(configs), tasks_per_profile=len(tasks), exact_cells=24,
             approximate_cells=12, engine_release=base['engine_release'])
path='configs/cross_rank_index.json'
(root/path).write_text(json.dumps(index, indent=2)+'\n', encoding='utf-8', newline='\n')
files.append(path)
checksums = ''.join(f'{hashlib.sha256((root/p).read_bytes()).hexdigest()}  {p}\n' for p in files)
(root/'CROSS_RANK_SHA256SUMS').write_text(checksums, encoding='utf-8', newline='\n')
release=hashlib.sha256(checksums.encode()).hexdigest()[:16]
archive=root/'packages'/f'cross-rank-{release}.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    for p in files+['CROSS_RANK_SHA256SUMS']: tar.add(root/p,arcname=p)
print(json.dumps(dict(release=release,archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),**index)))
