"""Submit the read-only snapshot, retaining the rejected no-job receipt."""
import json
from pathlib import Path
import subprocess

root=Path('/scratch/user/changze/lqr_experiments/results/final-story-20261024')
old=root/'submission-progress.json'
if old.exists():
    text=old.read_text().strip()
    if text.endswith('\\n'):text=text[:-2]
    data=json.loads(text)
    assert data['jobs']=={'progress':''},'Existing progress job; do not replay'
    rejected=dict(data,jobs={},status='Slurm rejected wrap argument; no job created')
    (root/'submission-progress-rejected.json').write_text(json.dumps(rejected,indent=2)+'\n')
receipt=dict(jobs={},requested_bound_SU=2/60,cpus=1,memory_MiB=1024,status='submitting')
old.write_text(json.dumps(receipt,indent=2)+'\n')
cmd=['sbatch','--parsable','-A','132685389143','-p','short','-t','2','--exclude=c136,c294',
     '-J','p2-final-progress','-o',str(root/'logs/progress-%j.out'),
     '/scratch/user/changze/lqr_experiments/releases/final-story-20261024/slurm/final_story_progress.sbatch']
job=subprocess.check_output(cmd,text=True).strip();assert job.isdigit()
receipt.update(jobs=dict(progress=job),status='submitted');old.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
