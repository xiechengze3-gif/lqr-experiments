"""Freeze only after the independent pilot passes; never overwrite a release."""
import argparse
import hashlib
import json
import platform
import shutil
import sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
import numba
import psutil
from dense_scaling import atomic_json


def freeze(out):
    dest=out/'frozen_config.json'
    if dest.exists():raise FileExistsError('A final configuration is already frozen')
    pilot=[json.loads(p.read_text()) for p in (out/'pilot-learning').glob('n*.json')]
    debug=[json.loads(p.read_text()) for p in (out/'debug').glob('n*.json')]
    if len(pilot)!=6 or len(debug)!=12 or any(d['meta']['status']!='completed' for d in pilot+debug):
        raise RuntimeError('Independent six-run pilot and twelve-run debug stability gates must pass')
    if not all(d['rows'][-1]['normalized_gap']<=.1 for d in pilot if d['meta']['method']!='dense'):
        raise RuntimeError('The common pilot precision target has not discriminated successfully')
    names=['dense_scaling.py','requirements.txt','scripts/npg_batched_collector.py',
        'scripts/direct_stein_final.py','scripts/final_round.py','scripts/test_direct_stein_final.py',
        'scripts/final_npg_audit.py','scripts/final_old_pi_audit.py','scripts/adaptive_rank.py',
        'scripts/adaptive_rank_run.py','scripts/npg_budget_system.py','scripts/freeze_final_round.py',
        'docs/FINAL_ROUND_PROTOCOL_20261014.md']
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    revision=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    blocks=[32768,131072,524288];total=8*3*8*sum(512+(b+1)*16 for b in blocks)
    fixed=[json.loads(p.read_text()) for p in (out/'pilot-fixed').glob('*.json')]
    warm=np.median([d['seconds']/d['physical_transitions'] for d in fixed])
    cfg=dict(title='Final matched Direct Stein damped PI',frozen_utc=datetime.now(timezone.utc).isoformat(),
        n=50,m=50,r=4,system_seeds=list(range(101,109)),sampling_seeds=[0],
        methods=['dense','known_rank','adaptive'],eta=.25,updates=8,horizon=16,burn=512,sigma=1.,
        blocks_per_update=blocks,primary_target=.1,initial_gap_tolerance=1e-10,
        solve_relative_residual_tolerance=1e-10,stability_radius_cutoff=1-1e-10,
        threshold_multiplier=1.,joint_block_weights=[1.,1.],workers=2,threads_per_worker=1,
        planned_core_trajectories=72,planned_core_transitions=total,
        warm_serial_hours=float(total*warm/3600),two_worker_hours_ideal=float(total*warm/7200),
        memory_plan_MB=1500,measured_free_memory_MB=float(psutil.virtual_memory().available/2**20),
        dependencies=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,numba=numba.__version__),
        source_revision_sha256=revision,sources=hashes,
        tests=dict(status='PASS',count=9,elapsed_seconds=1.564,
                   includes=['Gaussian sigma scaling','finite horizon and transposes','continuous collector equality',
                             'baseline and primitive budget','PSD and full-rank identity','RK clipping regression',
                             'zero-rank adaptive','numerical failure','interrupted checkpoint replay']),
        pilot=[dict(d['meta'],g=d['rows'][-1]['normalized_gap']) for d in pilot],
        policy='Fixed stage8 output. Costs are offline only. No backtracking. Failures retained. Unmet targets right censored.',
        output=str(out),cache='E:/ChatGPT/Cache/LQR_experiments/final-round-20261014',
        temp='E:/ChatGPT/Temp/LQR_experiments/final-round-20261014')
    atomic_json(dest,cfg)
    frozen=out/'frozen';frozen.mkdir(exist_ok=True)
    for name in names:
        path=frozen/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,path)
    shutil.copy2(dest,frozen/'config.json')
    (frozen/'SHA256SUMS').write_text('\n'.join(f'{h}  {name}' for name,h in hashes.items())+'\n')
    atomic_json(ROOT/'configs/final_round_20261014.json',cfg)
    print(json.dumps({k:cfg[k] for k in ('source_revision_sha256','planned_core_transitions','two_worker_hours_ideal','memory_plan_MB')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();freeze(a.output)
