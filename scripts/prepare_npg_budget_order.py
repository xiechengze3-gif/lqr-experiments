"""Prepare source, hashes, and predetermined budget grid; no numerical work."""
import hashlib
import json
import tarfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
stages,epoch=256,16
minimums=[4096,32768]
ranks=[1,2,4,8,16,32,50];seeds=list(range(4))
finals=[65536,131072,262144,524288,1048576,2097152]
profiles={f'min-{minimum}-final-{final}':dict(minimum_batch=minimum,final_batch=final)
          for minimum in minimums for final in finals}
schedules={name:[max(profile['minimum_batch'],profile['final_batch']//2**(stages//epoch-1-stage//epoch))
                 for stage in range(stages)] for name,profile in profiles.items()}
tasks=[dict(n=50,m=50,r=rank,system_seed=seed,trial_seed=0,final_batch=final,minimum_batch=minimum,
            schedule_id=f'min-{minimum}-final-{final}')
       for final in reversed(finals) for minimum in reversed(minimums) for seed in seeds for rank in ranks]
smoke=[i for i,t in enumerate(tasks) if t['final_batch']==min(finals) and t['minimum_batch']==max(minimums)
       and t['system_seed']==0 and t['r'] in (1,50)]
config=dict(profile='dense nested-rank total sample budget versus precision',engine_release='7f5c6de07fb244ab',
    n=50,ranks=ranks,system_seeds=seeds,methods=['raw','truncated'],stages=stages,epoch_length=epoch,
    minimum_batches=minimums,final_batches=finals,profiles=profiles,schedules=schedules,tasks=tasks,smoke_ids=smoke,
    step_multiplier=2.,horizon=16,sigma=1.,burn=1024,tolerances=[4.,2.,1.,.5,.25,.125],
    reference_margin=20.,rank_fit_max=16,primary_success='all four systems attain fixed-output absolute gap',
    protocol='A/Q/R/K0 fixed across ranks within seed; B nested rank with constant nonzero singular values. Predetermined schedule, same budget both methods; continuous per-arm trajectory; exact RK kept. No true cost stopping or learner model access.')
(root/'configs/npg_budget_order.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8',newline='\n')
files=['scripts/npg_budget_system.py','scripts/npg_budget_order.py','scripts/npg_budget_order_report.py',
       'scripts/prepare_npg_budget_order.py','scripts/npg_batched_collector.py','scripts/npg_precision_audit.py',
       'slurm/npg_budget_order.sbatch','slurm/npg_budget_archive.sbatch','scripts/submit_npg_budget_order.sh',
       'configs/npg_budget_order.json','docs/NPG_BUDGET_ORDER_PROTOCOL.md']
checksums=''.join(f'{hashlib.sha256((root/name).read_bytes()).hexdigest()}  {name}\n' for name in files)
(root/'NPG_BUDGET_SHA256SUMS').write_text(checksums,encoding='utf-8',newline='\n')
release=hashlib.sha256(checksums.encode()).hexdigest()[:16]
archive=root/'packages'/f'npg-budget-{release}.tar.gz'
with tarfile.open(archive,'w:gz') as handle:
    for name in [*files,'NPG_BUDGET_SHA256SUMS']:handle.add(root/name,arcname=name)
budgets={final:sum(config['burn']+(n+1)*config['horizon'] for n in schedule)
         for final,schedule in schedules.items()}
receipt=dict(release_id=release,archive=str(archive),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    configurations=len(tasks),methods=config['methods'],state='prepared',smoke_ids=smoke,
    remote_release=f'/scratch/user/changze/lqr_experiments/releases/npg-budget-{release}',
    remote_result=f'/scratch/user/changze/lqr_experiments/results/npg-budget-{release}',
    per_method_transition_budgets=budgets,
    campaign_planned_transitions=2*sum(budgets[t['schedule_id']] for t in tasks),
    planned_concurrency=24,local_result_target=f'E:/ChatGPT/Results/LQR_experiments/npg-budget-complete-{release}')
(root/'receipts'/f'npg-budget-{release}.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
