"""Submit one bounded report after every formal shard completes."""
import hashlib
import json
from pathlib import Path
import subprocess

root=Path('/scratch/user/changze/lqr_experiments/results/final-story-20261024')
release=Path('/scratch/user/changze/lqr_experiments/releases/final-story-20261024')
path=root/'submission-report.json';assert not path.exists(),'Inspect receipt; do not replay'
previous=sum(json.loads(p.read_text())['requested_bound_SU'] for p in root.glob('submission-*.json'))
assert previous+10/60<12
formal=json.loads((root/'submission-formal.json').read_text())['jobs']['formal']
files=['scripts/final_story_finalize.py','scripts/final_story_report.py','slurm/final_story_review.sbatch']
receipt=dict(jobs={},requested_bound_SU=10/60,prior_conservative_bound_SU=previous,total_cap_SU=12.,
    cpus=1,memory_MiB=2048,dependency='afterok:'+formal,
    threshold_sha256=hashlib.sha256((root/'threshold_frozen.json').read_bytes()).hexdigest(),
    source_sha256={p:hashlib.sha256((release/p).read_bytes()).hexdigest() for p in files})
path.write_text(json.dumps(receipt,indent=2)+'\n')
cmd=['sbatch','--parsable','-A','132685389143','-p','short','-t','10','--exclude=c136,c294',
    '--dependency=afterok:'+formal,'-J','p2-final-report','-o',str(root/'logs/report-%A_%a.out'),
    str(release/'slurm/final_story_review.sbatch'),'report']
job=subprocess.check_output(cmd,text=True).strip();assert job.isdigit()
receipt['jobs']['report']=job;path.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
