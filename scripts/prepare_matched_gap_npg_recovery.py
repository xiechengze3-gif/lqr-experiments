"""Capture a terminal timeout checkpoint before one bounded unchanged-source resume."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile


def read(path):
    return json.loads(path.read_text())


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--task',type=int,required=True)
    p.add_argument('--original-array',required=True)
    p.add_argument('--original-real-job',required=True)
    a=p.parse_args()
    c=read(a.root/'npg/resolved_config.json')
    plan=[(r,s) for s in c['confirm_seeds'] for r in c['ranks']]
    rank,seed=plan[a.task]
    stem='npg-r{0:03d}-s{1:04d}'.format(rank,seed)
    assert not (a.root/'npg/raw'/(stem+'.json')).exists()
    account=subprocess.check_output(['sacct','-j',a.original_real_job,'-n','-P',
        '--format=JobIDRaw,JobID,State,ExitCode,ElapsedRaw,AllocCPUS']).decode()
    originals=[v.split('|') for v in account.splitlines() if v.startswith(a.original_real_job+'|')]
    assert len(originals)==1
    original=originals[0]
    assert original[1]==a.original_array+'_'+str(a.task) and original[2]=='TIMEOUT'
    queue=subprocess.run(['squeue','-j',a.original_real_job,'-h'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert not queue.stdout.strip()
    assert queue.returncode==0 or (queue.returncode==1 and b'Invalid job id specified' in queue.stderr)
    cp=a.root/'npg/checkpoints'/(stem+'.npz')
    with zipfile.ZipFile(cp) as z:blob=z.read('meta.npy')
    size=2 if blob[6]==1 else 4;offset=8+size
    length=int.from_bytes(blob[8:offset],'little')
    meta=json.loads(blob[offset+length:].decode('utf-32le').rstrip('\0'))
    assert meta['identity']==c['identity']
    increments=[c['burn']+(n+1)*c['horizon'] for n,k in c['schedule_segments'] for _ in range(k)]
    stage=meta['next_stage'];assert 0<stage<len(increments)
    destination=a.root/'resource_adjustments'/('npg-recovery-'+a.original_real_job)
    assert not destination.exists(),'Recovery must not silently resubmit'
    destination.mkdir(parents=True)
    shutil.copyfile(cp,destination/'original-checkpoint.npz')
    (destination/'original-checkpoint-meta.json').write_text(json.dumps(meta,indent=2)+'\n')
    (destination/'original_sacct.txt').write_text(account)
    request=dict(route='npg',phase='confirm',rank=rank,seed=seed,task_id=a.task,
        original_array=a.original_array,original_real_job_id=a.original_real_job,
        original_state='TIMEOUT',checkpoint_stage=stage,remaining_updates=len(increments)-stage,
        queue_probe=dict(returncode=queue.returncode,stderr=queue.stderr.decode()),
        checkpoint_sha256=hashlib.sha256(cp.read_bytes()).hexdigest(),
        nominal_budget_at_checkpoint=sum(increments[:stage]),
        original_committed_physical_transitions=meta['physical'],
        extra_uncommitted_physical_transitions_bounds=[0,2*increments[stage]],
        extra_uncommitted_transitions_per_method_bounds={m:[0,increments[stage]] for m in ('dense','truncated')},
        uncertainty='Collector has no within-update journal. At most one unfinished paired update is discarded; its work is bounded, never asserted to be exactly zero.',
        source_and_schedule_unchanged=True,max_recovery_attempts=1,
        requested_minutes=30,requested_CPUs=1,requested_memory_MiB=2048,
        recovery_reservation_core_hours=.5,charged_against_existing_manual_recovery_allowance=10)
    (destination/'recovery_request.json').write_text(json.dumps(request,indent=2)+'\n')
    print(json.dumps(request))


if __name__=='__main__':main()
