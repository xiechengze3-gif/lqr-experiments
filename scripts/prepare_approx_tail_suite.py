"""Freeze the declared factorial controls; no local scientific computation."""
import ast
import hashlib
import json
import tarfile
from pathlib import Path


root = Path(__file__).resolve().parents[1]
tasks = []
for n in (25,50,75,100):
    ranks = (1,2,4,8,16) if n in (50,100) else (4,)
    for rank in ranks:
        settings = [('exact',0.,['relative']+(['singular','frobenius'] if n in (50,100) else []))]
        if n in (50,100):
            settings += [('singular',s,['singular']) for s in (.003,.01,.03,.1)]
            settings += [('frobenius',.1,['frobenius'])]
        settings += [('relative',a,['relative']) for a in (.01,.03,.05,.1,.3)]
        for mode,level,families in settings:
            for seed in (0,1):
                tasks.append(dict(id=len(tasks),n=n,m=n,r=rank,system_seed=seed,trial_seed=0,
                    tail_mode=mode,level=level,families=families,
                    cell=f'n{n}-r{rank}-{mode}-{level:g}'))
for n in (50,100):
    for seed in (0,1):
        tasks.append(dict(id=len(tasks),n=n,m=n,r=n,system_seed=seed,trial_seed=0,
                          tail_mode='exact',level=0.,families=['full_rank'],cell=f'n{n}-r{n}-exact-0'))
tasks.sort(key=lambda t:(-t['n'],-t['r'],t['system_seed'],t['tail_mode'],t['level']))
for task_id,task in enumerate(tasks):
    task['id']=task_id
profiles = {'ce':dict(algorithm='CE',budgets=[512*2**i for i in range(14)])}
for count in (32768,65536,131072,262144,524288,1048576,2097152,4194304):
    profiles[f'lspi-{count}'] = dict(algorithm='LSPI',schedule=[count]*6)
stages,epoch,minimum = 256,16,131072
for last in (131072,262144,524288,1048576,2097152):
    profiles[f'npg-{last}'] = dict(algorithm='NPG',schedule=[
        max(minimum,last//2**(stages//epoch-1-stage//epoch)) for stage in range(stages)],
        final_batch=last,minimum_batch=minimum,epoch_length=epoch)
smokes = [next(t['id'] for t in tasks if t['n']==100 and t['r']==rank and
              t['system_seed']==0 and t['tail_mode']==mode and t['level']==level)
          for rank,mode,level in ((1,'exact',0.),(100,'exact',0.),(4,'singular',.1),(16,'relative',.3))]
cfg = dict(schema=1,name='factorial tail/rank/dimension comparison',engine_release='7f5c6de07fb244ab',
    tasks=tasks,profiles=profiles,methods=['raw','truncated'],burn=1024,horizon=16,
    lspi_stages=6,npg_stages=stages,solver_rtol=1e-8,reference_cap=2048,
    smoke_stages=32,smoke_setting=dict(algorithm='NPG',schedule=[minimum]*32),
    reference_tolerance=1e-10,smoke_ids=smokes,tolerances=[5.,2.,1.,.5,.1,.03,.01],
    main_tail_singular=.01,relative_tails=[0.,.01,.03,.05,.1,.3],
    single_tails=[0.,.003,.01,.03,.1],absolute_fro_control=.1,
    ranks=[1,2,4,8,16],dimensions=[25,50,75,100],system_seeds=[0,1],
    protocol='Same A/Q/R/K0 and nested U/V across ranks and tails within n/seed. Unit head singular values. '
             'Dense costs and nonnormal A, open-loop unstable, common norm certificate and NPG eta. '
             'Unknown subspace; full critic LSPI then extracted block truncation; NPG only Z truncated. '
             'All scheduled fixed outputs, paired innovations, continuous state, exact RK. '
             'Population references diagnostic only; no true-cost stopping or acceptance. '
             'CE shared prefixes; all primitive transitions counted; unstable/solver/incomplete retained.')
path=root/'configs/approx_tail_suite.json'
path.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8',newline='\n')
files=['scripts/approx_tail_system.py','scripts/approx_tail_run.py','scripts/approx_tail_report.py',
       'scripts/prepare_approx_tail_suite.py','scripts/full_lstd.py','scripts/pi_ce_rank.py',
       'scripts/npg_batched_collector.py','slurm/approx_tail_suite.sbatch','slurm/approx_tail_archive.sbatch',
       'scripts/submit_approx_tail_suite.sh','configs/approx_tail_suite.json','docs/APPROX_TAIL_SUITE_PROTOCOL.md']
for name in files:
    if name.endswith('.py'):
        ast.parse((root/name).read_text(encoding='utf-8'),filename=name)
checksums=''.join(hashlib.sha256((root/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in files)
(root/'packages/APPROX_TAIL_SHA256SUMS').write_bytes(checksums.encode())
release=hashlib.sha256(checksums.encode()).hexdigest()[:16]
archive=root/'packages'/f'approx-tail-{release}.tar.gz'
with tarfile.open(archive,'w:gz') as handle:
    for name in files:
        handle.add(root/name,arcname=name)
    handle.add(root/'packages/APPROX_TAIL_SHA256SUMS',arcname='APPROX_TAIL_SHA256SUMS')
receipt=dict(release=release,state='prepared',tasks_per_profile=len(tasks),profiles=len(profiles),
    paired_configurations=len(tasks)*len(profiles),sampled_method_groups=2*len(tasks)*len(profiles),
    archive=str(archive),source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    remote_release=f'/scratch/user/changze/lqr_experiments/releases/approx-tail-{release}',
    remote_result=f'/scratch/user/changze/lqr_experiments/results/approx-tail-{release}',
    local_result_target=f'E:/ChatGPT/Results/LQR_experiments/approx-tail-complete-{release}',
    engine_release=cfg['engine_release'],smoke_ids=smokes,
    protocol='docs/APPROX_TAIL_SUITE_PROTOCOL.md',scientific_computation='Grace Slurm compute nodes',
    resource_caps='Initial CE8 cores, LSPI8 profiles each1x8 cores, NPG5 profiles each8x1 cores. Benchmark-supported scheduling caps may change; all scientific parameters frozen.',
    note='A/Q/R/K0 fixed across rank and tail; different system version from historical rank sweep; two system seeds, no population CI.')
(root/'receipts'/f'approx-tail-{release}.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt))
