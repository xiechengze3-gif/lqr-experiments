"""Freeze the added ranks without touching the original experiment release."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


def main():
    root = Path(__file__).resolve().parents[1]
    name = 'ce500-common-rank-extension-20261023-v2'
    cfg = json.loads((root / 'configs/ce500_common_constants_20261022.json').read_text())
    original = json.loads((root / 'analysis/ce500-common-constants-20261022/resolved_config.json').read_text())
    coarse = cfg['budgets'].copy()
    cfg.update(experiment=name, ranks=[70, 150, 300],
               output='/scratch/user/changze/lqr_experiments/results/'+name,
               cache='/scratch/user/changze/lqr_experiments/cache/'+name,
               temp='/scratch/user/changze/lqr_experiments/tmp/'+name,
               local_output=str(root / 'analysis' / name), base_output=original['output'],
               base_numerical_identity=original['identity'],
               diagnostic_probes=16, diagnostic_namespace=2026102308,
               coarse_reference_budgets=coarse,
               budgets=sorted(set(coarse + [98304, 163840, 196608, 229376, 294912, 327680, 360448, 393216, 458752])))
    cfg['resources'].update(total_SU_cap=85, formal_wall_minutes_maximum=45, report_wall_minutes=25,
                            extension_pilot_wall_minutes=40, diagnostic_wall_minutes=30, maximum_concurrency=12)
    manifest = 'configs/ce500_rank_extension_20261023.json'
    (root / manifest).write_text(json.dumps(cfg, indent=2)+'\n')
    sources = list(original['identity']['sources']) + ['scripts/ce500_common_constant_ops.py',
        'scripts/ce500_rank_extension.py', 'scripts/ce500_rank_diagnostic.py', 'scripts/ce500_rank_extension_ops.py',
        manifest, 'slurm/ce500_rank_extension.sbatch']
    package = root / 'packages' / name
    assert not package.exists(), 'Frozen release is immutable'
    hashes = {}
    for path in sources:
        data = (root / path).read_bytes().replace(b'\r\n', b'\n')
        if path.endswith('.py'): ast.parse(data)
        if path in original['identity']['sources']:
            assert hashlib.sha256(data).hexdigest() == original['identity']['sources'][path], path
        dest = package / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        hashes[path] = hashlib.sha256(data).hexdigest()
    (package / 'SHA256SUMS').write_bytes(''.join(value+'  '+key+'\n' for key,value in hashes.items()).encode())
    archive = root / 'packages' / (name+'.tar.gz')
    with tarfile.open(archive, 'w:gz') as tf: tf.add(package, arcname=name)
    receipt = dict(archive=str(archive), sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        files=hashes, bytes=archive.stat().st_size, local_E_free_bytes=shutil.disk_usage(root).free,
        ranks=cfg['ranks'], pilot_seeds=cfg['pilot_seeds'], formal_seeds=cfg['confirm_seeds'],
        budgets=cfg['budgets'], pilot_paired_datasets=6, formal_paired_datasets=90,
        formal_policy_rows=3*30*len(cfg['budgets'])*2, total_SU_cap=85, automatic_retries=0,
        scientific_grid_frozen_before_any_extension_sampling=True, common_grid_preserved=True,
        supersedes_unsubmitted_local_package='ce500-common-rank-extension-20261023-v1',
        measured_cost_basis='same n=500 engine; original rank32/500 tasks measured 26-30 minutes, 1CPU/2GiB; new pilot 40 minutes cap',
        pre_pilot_remaining_worst_case_SU=6*40/60+25/60+90*45/60+6*25/60+25/60+20/60+30/60+5)
    assert receipt['pre_pilot_remaining_worst_case_SU'] < 85
    (root/'receipts'/(name+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='files'},indent=2))


if __name__ == '__main__': main()
