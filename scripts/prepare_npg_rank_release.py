"""Source packaging and manifest construction only; no numerical simulation."""
import hashlib
import json
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cells = [(n, r) for n in (50, 100) for r in (1, 2, 4, 8, 16)]
cells += [(25, 4), (75, 4)]
# Small/large ranks interleaved in the queue; every cell has two matched systems.
tasks = [dict(n=n, m=n, r=r, system_seed=seed, trial_seed=0,
              family='coupled_unstable', tail=0., tail_shape='energy', stabilizer='isotropic')
         for seed in (0, 1) for n, r in cells]
schedule = [16384] * 8 + [65536] * 16 + [262144] * 24 + [1048576] * 32
config = dict(profile='end-to-end NPG rank scaling', engine_release='7f5c6de07fb244ab',
    tasks=tasks, stages=len(schedule), batch_schedule=schedule,
    horizon=16, sigma=1., burn=1024, step_multiplier=2., collector='batched_equivalent', tolerances=[5., 2., 1.],
    threshold_window=4, fit_max_rank_fraction=.2,
    protocol='Raw/truncated start at the identical full-rank isotropic K0; paired innovations, continuous state, fixed common schedule independent of n/r/method, exact RK retained. Exact references and true costs never enter learning or schedule selection. Count all primitive transitions; retain unstable and budget-censored runs.')
(root / 'configs/npg_rank_scaling.json').write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8', newline='\n')
files = ['scripts/npg_rank_scaling.py', 'scripts/npg_rank_report.py',
         'scripts/npg_batched_collector.py',
         'scripts/npg_precision_audit.py', 'slurm/npg_rank_scaling.sbatch',
         'configs/npg_rank_scaling.json', 'docs/NPG_RANK_SCALING_PROTOCOL.md',
         'scripts/prepare_npg_rank_release.py']
checksums = ''.join(f'{hashlib.sha256((root / p).read_bytes()).hexdigest()}  {p}\n' for p in files)
(root / 'NPG_RANK_SHA256SUMS').write_text(checksums, encoding='utf-8', newline='\n')
release = hashlib.sha256(checksums.encode()).hexdigest()[:16]
archive = root / 'packages' / f'npg-rank-{release}.tar.gz'
with tarfile.open(archive, 'w:gz') as handle:
    for name in [*files, 'NPG_RANK_SHA256SUMS']:
        handle.add(root / name, arcname=name)
print(json.dumps(dict(release_id=release, archive=str(archive), archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), tasks=len(tasks))))
