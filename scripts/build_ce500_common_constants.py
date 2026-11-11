"""Freeze the common-system-constant CE experiment and numerical closure."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


def main():
    root=Path(__file__).resolve().parents[1];name='ce500-common-constants-20261022'
    files=['dense_scaling.py','scripts/rank_sweep100.py','scripts/actuation_redundancy.py',
        'scripts/npg_batched_collector.py','scripts/direct_stein_final.py','scripts/ce_matched_initial_gap.py',
        'scripts/ce500_matched_gap.py','scripts/common_constant_spectrum_preflight.py',
        'scripts/ce500_common_constants.py','scripts/ce500_common_constant_prepare.py',
        'scripts/ce500_common_constant_report.py','scripts/ce500_common_constant_ops.py',
        'configs/ce500_common_constants_20261022.json','slurm/ce500_common_constants.sbatch']
    cfg=json.loads((root/'configs/ce500_common_constants_20261022.json').read_text())
    assert cfg['budgets']==[2048*2**i for i in range(11)]
    assert cfg['primary_absolute_target']==.1 and cfg['supplied_common_bounds']['p_0']==47
    assert len(cfg['confirm_seeds'])==30 and cfg['resources']['automatic_retries']==0
    package=root/'packages'/name;assert not package.exists(),'Frozen packages are immutable';hashes={}
    for f in files:
        source=root/f
        if f.endswith('.py'):ast.parse(source.read_text(encoding='utf-8'))
        data=source.read_bytes().replace(b'\r\n',b'\n');dest=package/f
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);hashes[f]=hashlib.sha256(data).hexdigest()
    (package/'SHA256SUMS').write_bytes(''.join(v+'  '+k+'\n' for k,v in hashes.items()).encode())
    archive=root/'packages'/(name+'.tar.gz')
    with tarfile.open(archive,'w:gz') as tar:tar.add(package,arcname=name)
    receipt=dict(status='frozen',archive=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        bytes=archive.stat().st_size,sources=hashes,free_E_bytes=shutil.disk_usage(root).free,
        paired_formal_datasets=150,paired_pilot_datasets=10,common_sample_prefixes=len(cfg['budgets']),
        expected_formal_policy_rows=3300,expected_unique_formal_policies=2970,
        total_SU_cap=cfg['resources']['total_SU_cap'],automatic_retries=0,
        scientific_grid_frozen_before_new_pilot_sampling=True,
        progression='preflight measured collector/solver and exact resume -> 2-seed pilot -> independent audit -> measured 30-seed formal -> 6 audit shards -> same-accuracy rank scaling report')
    (root/'receipts'/(name+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='sources'},indent=2))


if __name__=='__main__':main()
