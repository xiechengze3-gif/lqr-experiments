"""Inspect and resume the original frozen CE run, preserving all failed work."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zipfile


def read(p):return json.loads(p.read_text())


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def metadata(path):
    # Only parse the small Unicode metadata array; no numeric work on login node.
    with zipfile.ZipFile(path) as z:data=z.read('meta.npy')
    assert data[:6]==b'\x93NUMPY'
    if data[6]==1:offset=10;length=struct.unpack('<H',data[8:10])[0]
    else:offset=12;length=struct.unpack('<I',data[8:12])[0]
    header=ast.literal_eval(data[offset:offset+length].decode('latin1'))
    assert header['shape']==() and header['descr'].startswith('<U')
    return json.loads(data[offset+length:].decode('utf-32-le').rstrip('\x00'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--submit-resume',action='store_true');a=p.parse_args()
    cfg=read(a.manifest);out=Path(cfg['output']);release=a.manifest.resolve().parents[1]
    task_id=82;rank=32;seed=216;failed='20205483';stem='ce-r032-s0216'
    path=out/'checkpoints'/(stem+'.npz');meta=metadata(path)
    assert meta['identity']==read(out/'verification.json')['identity']
    assert meta['done']==786432 and len(meta['rows'])==28
    plan=read(out/'formal_plan.json');assert plan['budgets'][-1]==1048576
    assert not (out/'raw'/(stem+'.json')).exists()
    for q in meta['rows']:
        assert sha(out/q['policy_file'])==q['policy_sha256']
    assert all(q['stable'] and q['gap']<=.05 for q in meta['rows'][-2:])
    states=subprocess.check_output(['sacct','-j',failed,'-X','-n','-P','-o','JobIDRaw,State,ElapsedRaw'],universal_newlines=True)
    assert states.strip().split('|')[1]=='TIMEOUT'
    formal=read(out/'formal_submission.json')
    ledger=subprocess.check_output(['sacct','-j',','.join(formal['arrays_by_rank'].values()),'-X','-n','-P',
        '-o','JobIDRaw,JobID,State,ElapsedRaw'],universal_newlines=True)
    released=0.;closed=0
    for line in ledger.splitlines():
        fields=line.split('|')
        if len(fields)<4 or fields[2] not in ('COMPLETED','TIMEOUT'):continue
        idx=int(fields[1].rsplit('_',1)[1]);r=cfg['ranks'][idx%5]
        released+=(plan['formal_wall_minutes_by_rank'][str(r)]*60-int(fields[3]))/3600;closed+=1
    result=dict(status='checkpoint_verified',failed_job_id=failed,original_array='20204703',task_id=task_id,rank=rank,seed=seed,
        checkpoint_sha256=sha(path),identity=meta['identity'],committed_OLS_samples=meta['done'],
        committed_primitive_transitions=meta['done']+cfg['burn'],remaining_OLS_samples=1048576-meta['done'],
        discarded_uncommitted_transition_lower_bound=0,discarded_uncommitted_transition_upper_bound=1048576-meta['done'],
        discarded_count_is_not_exact=True,committed_budget_points=14,
        both_targets_attained_before_failure_for_this_seed=True,
        last_committed_gaps={q['method']:q['gap'] for q in meta['rows'][-2:]},
        closed_formal_attempts=closed,released_original_wall_limit_core_hours=released,
        original_initial_SU_bound=59.885,resume_wall_minutes=10,
        revised_bound_with_one_resume_and_same_scope_auxiliary_replacements=59.885-released+10/60,
        justification='Same frozen learner/config/RNG/Gram/state; resume last262144OLS only; keep all30seeds/all15budgets/full4050policy audit. Failed and cancelled dependent jobs retained.',
        source_sha256=sha(Path(__file__)))
    assert result['revised_bound_with_one_resume_and_same_scope_auxiliary_replacements']<60
    if a.submit_resume:
        destination=out/'recovery_plan.json';assert not destination.exists(),'At most one resume for this task'
        destination.write_text(json.dumps(result,indent=2)+'\n')
        command=['sbatch','--parsable','-A',cfg['resources']['account'],'-p','short','-t','00:10:00',
            '--array=82','-J','ce500-resume-r32-s216','-o',str(out/'logs/resume-%A_%a.out'),
            'slurm/ce500_matched_gap.sbatch','task','confirm','--plan',str(out/'formal_plan.json')]
        job=subprocess.check_output(command,cwd=str(release),universal_newlines=True).strip();assert job.isdigit()
        result.update(status='resume_submitted',resume_array=job,manual_resumes_for_task=1)
        destination.write_text(json.dumps(result,indent=2)+'\n')
    else:(out/'recovery_inspection.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
