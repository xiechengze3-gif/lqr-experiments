"""Submit final archive, omitting verified completed jobs from Slurm dependencies."""
import argparse
import json
from pathlib import Path
import subprocess


def read(p):return json.loads(p.read_text())


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    cfg=read(a.manifest);out=Path(cfg['output']);release=a.manifest.resolve().parents[1]
    receipt=out/'final_bundle_submission.json'
    if receipt.exists():
        prior=read(receipt);assert not prior['final_bundle_job'],'A valid final job already exists'
        prior['submission_failure']='Slurm Job dependency problem: completed common archive already purged from controller'
        prior['nonexistent_job_not_charged']=True
        old=out/'final_bundle_submission_attempt1.json';assert not old.exists()
        old.write_text(json.dumps(prior,indent=2)+'\n');receipt.unlink()
    formal=read(out/'formal_submission.json')
    wanted=[formal['formal_report'],formal['identification_audit']]+[q['job_id'] for q in formal['bundle_jobs']]
    wanted += [read(out/'common_bundle_submission.json')['common_bundle_job']]
    output=subprocess.check_output(['sacct','-j',','.join(wanted),'-X','-n','-P','-o','JobIDRaw,State'],universal_newlines=True)
    states={line.split('|')[0]:line.split('|')[1] for line in output.splitlines() if line.strip()}
    assert all(states.get(job) in ('PENDING','RUNNING','COMPLETING','COMPLETED') for job in wanted),states
    active=[job for job in wanted if states[job]!='COMPLETED']
    command=['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short','-t','00:10:00',
        '--begin=now+1minute','-J','ce500-final-archive','-o',str(out.parent.parent/'accounting'/cfg['experiment']/'final-archive-%j.out')]
    if active:command+=['--dependency=afterok:'+':'.join(active)]
    result=subprocess.run(command+['slurm/ce500_finish.sbatch'],cwd=str(release),stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    assert result.returncode==0 and result.stdout.strip().isdigit(),(result.returncode,result.stdout,result.stderr)
    record=dict(final_bundle_job=result.stdout.strip(),expected_pre_final_jobs=186,wall_minutes=10,
        included_in_60SU_cap=True,active_dependencies=active,
        completed_dependencies_omitted=[job for job in wanted if states[job]=='COMPLETED'],prior_unsubmitted_failure_preserved=True)
    receipt.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))


if __name__=='__main__':main()
