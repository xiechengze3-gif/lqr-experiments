"""Freeze source/plan only; no numerical simulation or analysis."""
import ast
import hashlib
import json
import tarfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
files=['scripts/npg_300_feasibility.py','slurm/npg_300_feasibility.sbatch',
       'scripts/prepare_npg_300_feasibility.py','docs/NPG_REPLICATION_300_PLAN_20261009.md']
ast.parse((root/files[0]).read_text())
checksums=''.join(f'{hashlib.sha256((root/name).read_bytes()).hexdigest()}  {name}\n' for name in files)
manifest=root/'packages/FEASIBILITY_SHA256SUMS'
manifest.write_text(checksums,encoding='utf-8',newline='\n')
release=hashlib.sha256(checksums.encode()).hexdigest()[:16]
archive=root/f'packages/npg-300-feasibility-{release}.tar.gz'
with tarfile.open(archive,'w:gz') as handle:
    for name in files:handle.add(root/name,arcname=name)
    handle.add(manifest,arcname='FEASIBILITY_SHA256SUMS')
receipt=dict(release_id=release,state='prepared',scope='single-system feasibility; no formal replicated run yet',
    archive=str(archive),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    remote_release=f'/scratch/user/changze/lqr_experiments/releases/npg-300-feasibility-{release}',
    remote_result=f'/scratch/user/changze/lqr_experiments/results/npg-300-feasibility-{release}',
    engine_release='7f5c6de07fb244ab',system_collector_release='e93b7ffa7fca793e',
    system_seed=0,dimension=300,ranks=[1,4,16,64,300],reference_ranks=[1,16,300],
    reference_stages=256,collector_dimensions=[50,100,300],collector_rank=4,
    collector_prefixes=[4096,16384,65536],collector_horizon=16,
    cpus=8,memory='8G',time_limit='02:00:00',science_location='Grace Slurm compute nodes',
    local_result_target=f'E:/ChatGPT/Results/LQR_experiments/npg-300-feasibility-{release}')
(root/f'receipts/npg-300-feasibility-{release}.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
