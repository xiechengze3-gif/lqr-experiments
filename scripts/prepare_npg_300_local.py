"""Freeze the published collector/system and enable explicitly authorized local runs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = Path(r'E:\ChatGPT\Results\LQR_experiments\npg-budget-complete-e93b7ffa7fca793e\npg-budget-e93b7ffa7fca793e')
DEST = ROOT / 'local_runs' / 'npg300-20261009' / 'engine'


def prepare():
    DEST.mkdir(parents=True, exist_ok=True)
    sources = {
        'dense_scaling.py': BASE / 'engine' / 'dense_scaling.py',
        'npg_budget_system.py': BASE / 'source' / 'scripts' / 'npg_budget_system.py',
        'npg_batched_collector.py': BASE / 'source' / 'scripts' / 'npg_batched_collector.py',
        'npg_300_feasibility.py': ROOT / 'scripts' / 'npg_300_feasibility.py',
    }
    records = []
    for name, src in sources.items():
        original = src.read_bytes()
        content = original.decode('utf-8').replace('\r\n', '\n')
        if name == 'dense_scaling.py':
            old = 'if not os.environ.get("SLURM_JOB_ID"):'
            assert content.count(old) == 1
            content = content.replace(old, 'if not (os.environ.get("SLURM_JOB_ID") or os.environ.get("LQR_COMPUTE_BACKEND") == "local"):')
            content = content.replace('All simulations, verification and numerical reporting require Grace Slurm compute nodes', 'Numerical work requires Slurm or explicitly authorized LQR_COMPUTE_BACKEND=local')
        elif name == 'npg_300_feasibility.py':
            content = content.replace("job_id=os.environ['SLURM_JOB_ID']", "job_id=None,execution_backend='local',pid=os.getpid()")
            content = content.replace('Fixed eight BLAS threads for cost measurements', 'Two BLAS threads for local cost measurements')
        path = DEST / name
        path.write_text(content, encoding='utf-8', newline='\n')
        records.append(dict(file=name,original_path=str(src),original_sha256=hashlib.sha256(original).hexdigest(),
                            local_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    info = dict(execution_backend='local',authorization='User explicitly requested local execution on 2026-10-09.',
                base_release='e93b7ffa7fca793e',changes='Execution guard and metadata only; system and collector numerical algorithms unchanged.',sources=records)
    (DEST.parent / 'source_provenance.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(info,indent=2))


if __name__ == '__main__':
    prepare()
