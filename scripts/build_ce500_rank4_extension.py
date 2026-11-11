"""Freeze the extension package using only existing files and stdlib."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'ce500-rank4-extension-20261020'
BASE = '/scratch/user/changze/lqr_experiments'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    old = Path('E:/ChatGPT/Results/LQR_experiments/ce500-matched-gap-20261019')
    cfg = json.loads((ROOT/'configs/ce500_matched_gap_20261019.json').read_text(encoding='utf-8'))
    verification = json.loads((old/'verification.json').read_text(encoding='utf-8'))
    cfg.update(experiment=NAME, ranks=[4], source_output=cfg['output'],
        source_local_output=str(old), source_manifest_sha256=sha(old/'artifact_sha256.json'),
        source_system_sha256=sha(old/'systems/r002.npz'), source_numeric_sha256=verification['identity']['sources'],
        output=BASE+'/results/'+NAME, cache=BASE+'/cache/'+NAME, temp=BASE+'/tmp/'+NAME,
        local_output='E:/ChatGPT/Results/LQR_experiments/'+NAME,
        pilot_budgets=[2048,8192,32768,131072],
        confirm_budgets=json.loads((old/'formal_plan.json').read_text(encoding='utf-8'))['budgets'])
    cfg['resources'].update(total_SU_cap=20, max_concurrency=30, manual_resumes_overall_maximum=5,
        preflight_wall_minutes=10, pilot_provisional_wall_minutes=10, formal_wall_minutes=25,
        audit_wall_minutes=30, identification_wall_minutes=10, archive_wall_minutes=10,
        excluded_hosts=['c136','c294'], initial_requested_SU_envelope=14.50,
        expected_actual_SU_interval=[9,12], reuse_existing_AMS_measurements=True)
    config = ROOT/'configs/ce500_rank4_extension_20261020.json'
    config.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
    source = list(cfg['source_numeric_sha256']) + ['scripts/ce500_rank4_extension.py',
        'scripts/ce500_rank_scaling_report.py','scripts/ce500_identification_audit.py',
        'scripts/collect_matched_gap_settlement.py','scripts/account_rank_sweep100.py',
        'configs/ce500_rank4_extension_20261020.json','slurm/ce500_rank4_extension.sbatch',
        'docs/CE500_RANK4_EXTENSION_20261020.md']
    package = ROOT/'packages'/NAME
    assert not package.exists(), 'Do not replace an existing frozen package'
    for name in source:
        path = ROOT/name
        if name in cfg['source_numeric_sha256']:
            assert sha(path)==cfg['source_numeric_sha256'][name], name
        if name.endswith('.py'): ast.parse(path.read_text(encoding='utf-8'),filename=name)
        dest = package/name; dest.parent.mkdir(parents=True,exist_ok=True)
        # Preserve old numerical source bytes. New Slurm helper needs UNIX newlines.
        if name.endswith('.sbatch'):
            dest.write_bytes(path.read_bytes().replace(b'\r\n',b'\n'))
        else: shutil.copyfile(path,dest)
    (package/'SHA256SUMS').write_bytes(''.join(sha(package/n)+'  '+n+'\n' for n in source).encode('utf-8'))
    archive = ROOT/'packages'/(NAME+'.tar.gz')
    with tarfile.open(archive,'w:gz') as t: t.add(package,arcname=NAME)
    receipt = dict(experiment=NAME,archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,
        numeric_source_files_bitwise_equal_to_original=True,local_free_bytes=shutil.disk_usage(ROOT).free,
        local_output=cfg['local_output'],remote_output=cfg['output'],SU_cap=20)
    (ROOT/'receipts'/(NAME+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__': main()
