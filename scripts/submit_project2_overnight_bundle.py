"""Submit complete 760-task coverage in 64 unchanged-science bundles."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/project2-overnight-20261020'
OPS=BASE/'releases/project2-overnight-ops-v2'


def main():
    path=OUT/'submission-formal.json';receipt=json.loads(path.read_text())
    assert 'mechanism' not in receipt['jobs'] and 'mechanism-bundles' not in receipt['jobs']
    existing=subprocess.check_output(['squeue','-h','-u','changze','--name=p2-night-mechanism,p2-night-mechanism-bundles','-o','%i %j'],universal_newlines=True)
    assert not existing.strip(),'Inspect existing tasks before resubmission'
    checks=list((OUT/'mechanism-preflight/mechanism').glob('task-*.json'))
    assert len(checks)==3 and all(len(json.loads(p.read_text())['rows'])==27 for p in checks)
    assert len(json.loads((OUT/'formal_plan.json').read_text())['mechanism_tasks'])==760
    receipt['scheduling_amendment']=dict(reason='760-element submission rejected by QOSMaxSubmitJobPerUserLimit, no job id or formal output; verified squeue before bundling',
        logical_tasks=760,bundles=64,bundle_size=12,cpus=1,memory_MiB=2048,wall_minutes=5,
        maximum_concurrency=24,science_source_changed=False,random_streams_and_seeds_changed=False,
        complete_coverage=list(range(760)),original_mechanism_bound_SU=760*2/60,
        new_mechanism_bound_SU=64*5/60,epoch=time.time())
    receipt['SU_bounds']['formal_mechanism']=64*5/60
    receipt['total_worst_case_SU_bound']=sum(receipt['SU_bounds'].values())
    assert receipt['total_worst_case_SU_bound']<100
    path.write_text(json.dumps(receipt,indent=2)+'\n')
    cmd=['sbatch','--parsable','-A','132685389143','-p','short','--exclude=c136,c294',
         '-t','5','--array=0-63%24','-J','p2-night-mechanism-bundles',
         '-o',str(OUT/'logs/mechanism-bundle-%A_%a.out'),str(OPS/'slurm/project2_overnight_bundle.sbatch')]
    job=subprocess.check_output(cmd,cwd=OPS,universal_newlines=True).strip();assert job.isdigit(),job
    receipt['jobs']['mechanism-bundles']=job;receipt['status']='formal_actor_and_bundled_mechanism_submitted'
    path.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='scheduling_amendment'},indent=2))


if __name__=='__main__':main()
