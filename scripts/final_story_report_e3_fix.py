"""One bounded report-only recovery; frozen learning outputs are untouched."""
import hashlib
import json
from pathlib import Path
import subprocess

root=Path('/scratch/user/changze/lqr_experiments/results/final-story-20261024')
release=root.parent.parent/'releases/final-story-20261024'
path=root/'submission-report-e3-fix.json';assert not path.exists(),'Inspect receipt, no automatic retry'
old=json.loads((root/'submission-report-recovery.json').read_text())['jobs']['report-recovery']
state=subprocess.check_output(['sacct','-X','-j',old,'-n','-P','--format=State'],text=True).strip()
assert state.startswith('FAILED'),state
previous=sum(json.loads(p.read_text())['requested_bound_SU'] for p in root.glob('submission-*.json'))
assert previous+10/60<12
partial={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'report').glob('*.csv')}
if not (root/'report_partial_numeric_sha256.json').exists():
    (root/'report_partial_numeric_sha256.json').write_text(json.dumps(partial,indent=2)+'\n')
files=['scripts/final_story_finalize.py','scripts/final_story_report_v3.py','scripts/final_story_robustness.py','slurm/final_story_review.sbatch']
receipt=dict(jobs={},requested_bound_SU=10/60,prior_bound_SU=previous,total_cap_SU=12.,
    reason='Evaluate perturbed stationary costs directly: nominal Jstar is not a lower bound for a changed plant. Signed cost improvements are valid.',
    learning_outputs_changed=False,learning_restarted=False,
    source_sha256={p:hashlib.sha256((release/p).read_bytes()).hexdigest() for p in files})
path.write_text(json.dumps(receipt,indent=2)+'\n')
cmd=['sbatch','--parsable','-A','132685389143','-p','short','-t','10','--exclude=c136,c294',
     '-J','p2-final-report-e3-fix','-o',str(root/'logs/report-e3-fix-%A_%a.out'),
     str(release/'slurm/final_story_review.sbatch'),'report']
job=subprocess.check_output(cmd,text=True).strip();assert job.isdigit()
receipt['jobs']['report-e3-fix']=job;path.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
