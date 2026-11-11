"""Prepare immutable config/source archive; no local numerical experiment."""
import ast
import hashlib
import json
import tarfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
tasks=[]
for n in (25,50,75,100):
    ranks=(1,2,4,8,16,n) if n in (50,100) else (4,)
    for rank in ranks:
        modes=[('exact',0.)]
        if n in (50,100) and rank<n:
            modes.append(('frobenius',.03))
        for mode,level in modes:
            for seed in range(10):
                tasks.append(dict(id=len(tasks),n=n,m=n,r=rank,system_seed=seed,trial_seed=0,
                    tail_mode=mode,level=level,families=['rank_precision'],cell=f'n{n}-r{rank}-{mode}-{level:g}'))
# Small cases finish first within each shard, but no outcomes select the ordering.
tasks.sort(key=lambda t:(t['n'],t['tail_mode'],t['system_seed'],t['r']))
for task_id,task in enumerate(tasks):
    task['id']=task_id
profiles={'ce':dict(algorithm='CE',budgets=[512*2**i for i in range(16)])}
for count in (32768*2**i for i in range(10)):
    profiles[f'lspi-{count}']=dict(algorithm='LSPI',schedule=[count]*6)
for last in (131072,524288,2097152,8388608,33554432):
    minimum=max(131072,last//16)
    profiles[f'npg-{last}']=dict(algorithm='NPG',schedule=[max(minimum,last//2**(15-stage//16)) for stage in range(256)],
                               final_batch=last,minimum_batch=minimum,epoch_length=16)
cfg=dict(schema=1,name='10-system rank/precision comparison',engine_release='7f5c6de07fb244ab',
    tasks=tasks,profiles=profiles,system_seeds=list(range(10)),ranks=[1,2,4,8,16],dimensions=[25,50,75,100],
    methods=['raw','truncated'],burn=1024,horizon=16,lspi_stages=6,npg_stages=256,
    solver_rtol=1e-8,reference_cap=2048,reference_tolerance=1e-10,tail_frobenius=.03,
    tolerances=[5.,2.,1.,.5,.3,.1,.03,.01,.003],primary_tolerances=[.03,.01,.003],
    success_fractions=[.8,.9,1.],primary_success_fraction=.8,bootstrap_replicates=500,
    scientific_computation='Grace Slurm compute nodes',
    oracle_stability_termination_disclosed=True,protocol='docs/RANK_MULTISEED_PROTOCOL.md')
path=root/'configs/rank_multiseed.json'
path.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8',newline='\n')
files=['scripts/rank_multiseed_run.py','scripts/rank_multiseed_report.py','scripts/prepare_rank_multiseed.py',
       'scripts/rank_multiseed_report_audit.py',
       'scripts/approx_tail_run.py','scripts/approx_tail_system.py','scripts/full_lstd.py',
       'scripts/pi_ce_rank.py','scripts/npg_batched_collector.py','scripts/submit_rank_multiseed.sh',
       'slurm/rank_multiseed.sbatch','slurm/rank_multiseed_archive.sbatch',
       'configs/rank_multiseed.json','docs/RANK_MULTISEED_PROTOCOL.md']
for name in files:
    if name.endswith('.py'):
        ast.parse((root/name).read_text(encoding='utf-8'),filename=name)
checksums=''.join(hashlib.sha256((root/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in files)
(root/'packages/RANK_MULTISEED_SHA256SUMS').write_bytes(checksums.encode())
release=hashlib.sha256(checksums.encode()).hexdigest()[:16]
archive=root/'packages'/f'rank-multiseed-{release}.tar.gz'
with tarfile.open(archive,'w:gz') as handle:
    for name in files:
        handle.add(root/name,arcname=name)
    handle.add(root/'packages/RANK_MULTISEED_SHA256SUMS',arcname='RANK_MULTISEED_SHA256SUMS')
receipt=dict(release=release,state='prepared',systems=len(tasks),profiles=len(profiles),
    paired_configurations=len(tasks)*len(profiles),sampled_method_groups=2*len(tasks)*len(profiles),
    archive=str(archive),source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    remote_release=f'/scratch/user/changze/lqr_experiments/releases/rank-multiseed-{release}',
    remote_result=f'/scratch/user/changze/lqr_experiments/results/rank-multiseed-{release}',
    local_result_target=f'E:/ChatGPT/Results/LQR_experiments/rank-multiseed-complete-{release}',
    engine_release=cfg['engine_release'],system_seeds=cfg['system_seeds'],primary_tolerances=cfg['primary_tolerances'],
    primary_success_fraction=.8,scientific_computation=cfg['scientific_computation'],
    resource_caps='128 cores total maximum; 432 shard units plus reporting jobs; own-shard bounded requeue16',
    oracle_stability_termination_disclosed=True,protocol=cfg['protocol'])
(root/'receipts'/f'rank-multiseed-{release}.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt))
