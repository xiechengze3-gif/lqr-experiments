"""Prepare immutable pilot source and schedule manifest; no simulation."""
import hashlib
import json
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
stages,epoch_length,minimum = 128,16,16384
final_batches = [262144,1048576]
schedules = {}
for final in final_batches:
    geometric = [max(minimum, final//2**(7-stage//epoch_length)) for stage in range(stages)]
    average = sum(geometric)//stages
    assert average*stages == sum(geometric)
    schedules[f'geometric-{final}'] = geometric
    schedules[f'constant-{final}'] = [average]*stages
tasks = []
for final in reversed(final_batches):
    for seed in (0,1):
        for rank in (1,4):
            for shape in ('geometric','constant'):
                tasks.append(dict(n=50,m=50,r=rank,system_seed=seed,trial_seed=0,
                    family='coupled_unstable',tail=0.,tail_shape='energy',stabilizer='isotropic',
                    final_batch_label=final,schedule_kind=shape,schedule_id=f'{shape}-{final}'))
config = dict(profile='equal-total-budget epoch NPG pilot',engine_release='7f5c6de07fb244ab',
    methods=['raw','truncated'],stages=stages,epoch_length=epoch_length,minimum_batch=minimum,
    final_batches=final_batches,schedules=schedules,tasks=tasks,step_multiplier=2.,
    horizon=16,sigma=1.,burn=1024,tolerances=[.25,.5,1.,2.],threshold_window=4,
    primary_output='fixed stage 128; evaluate all predeclared absolute tolerances',
    protocol='Epoch schedule is predetermined, not data-adaptive. Constant and geometric arms have exactly equal total transitions per budget tier. Both methods scan both tiers independently; no n/r budget ratio is imposed. Truth only evaluates. Continuous trajectory; exact RK retained; unstable runs remain failures. Two system seeds support a pilot only.')
(root/'configs/npg_epoch_budget.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8',newline='\n')
files=['scripts/npg_epoch_budget.py','scripts/npg_epoch_report.py','scripts/npg_batched_collector.py',
       'scripts/npg_precision_audit.py','scripts/prepare_npg_epoch_release.py',
       'slurm/npg_epoch_budget.sbatch','configs/npg_epoch_budget.json','docs/NPG_EPOCH_BUDGET_PROTOCOL.md']
checksums=''.join(f'{hashlib.sha256((root/name).read_bytes()).hexdigest()}  {name}\n' for name in files)
(root/'NPG_EPOCH_SHA256SUMS').write_text(checksums,encoding='utf-8',newline='\n')
release=hashlib.sha256(checksums.encode()).hexdigest()[:16]
archive=root/'packages'/f'npg-epoch-{release}.tar.gz'
with tarfile.open(archive,'w:gz') as handle:
    for name in [*files,'NPG_EPOCH_SHA256SUMS']:handle.add(root/name,arcname=name)
receipt=dict(release_id=release,archive=str(archive),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    configurations=len(tasks),methods=config['methods'],state='prepared',
    remote_release=f'/scratch/user/changze/lqr_experiments/releases/npg-epoch-{release}',
    remote_result=f'/scratch/user/changze/lqr_experiments/results/npg-epoch-{release}')
(root/'receipts'/f'npg-epoch-{release}.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
