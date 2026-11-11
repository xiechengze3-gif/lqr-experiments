"""Freeze only the additional prospective near-threshold measurement."""
import ast
import hashlib
import json
from pathlib import Path
import tarfile


root=Path(__file__).resolve().parents[1];name='ce500-r300-fine-20261023-v1'
cfg=dict(experiment=name,base_release='/scratch/user/changze/lqr_experiments/releases/ce500-common-rank-extension-20261023-v2',
         base_output='/scratch/user/changze/lqr_experiments/results/ce500-common-rank-extension-20261023-v2',
         output='/scratch/user/changze/lqr_experiments/results/'+name,
         budgets=list(range(393216,458753,8192)),pilot_seeds=[700,701],confirm_seeds=list(range(800,830)),
         absolute_target=.1,rank=300,automatic_retries=0,
         supplement_worst_case_SU_bound=32*12/60+5/60+10/60+1,
         combined_extension_cap_SU=85,grid_chosen_after_pilot_prefixes_before_fine_sampling=True)
assert cfg['supplement_worst_case_SU_bound']<8
manifest='configs/ce500_r300_fine_20261023.json';(root/manifest).write_text(json.dumps(cfg,indent=2)+'\n')
dest=root/'packages'/name;assert not dest.exists();hashes={}
for p in ['scripts/ce500_r300_fine.py','scripts/ce500_r300_fine_ops.py','slurm/ce500_r300_fine.sbatch',manifest]:
    data=(root/p).read_bytes().replace(b'\r\n',b'\n')
    if p.endswith('.py'):ast.parse(data)
    target=dest/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);hashes[p]=hashlib.sha256(data).hexdigest()
(dest/'SHA256SUMS').write_bytes(''.join(v+'  '+k+'\n' for k,v in hashes.items()).encode())
archive=root/'packages'/(name+'.tar.gz')
with tarfile.open(archive,'w:gz') as t:t.add(dest,arcname=name)
receipt=dict(archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=hashes,
             supplement_worst_case_SU_bound=cfg['supplement_worst_case_SU_bound'],budgets=cfg['budgets'])
(root/'receipts'/(name+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
