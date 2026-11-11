"""Correct a hard-coded shared-runner backend label; preserve all numerical data."""
import hashlib
import json
import os
import shutil
from pathlib import Path

ROOT=Path('/scratch/user/changze/lqr_experiments/results')
for name,job in [('rank-sweep100-20261016','20174848'),
                 ('rank-sweep100-final-20261016','20175111'),
                 ('rank-sweep100-confirm-20261016','20175274')]:
    path=ROOT/name/'verification.json'
    data=json.loads(path.read_text())
    if data['execution']['backend']=='grace_slurm':continue
    backup=path.with_name('verification_original_backend_label.json')
    assert not backup.exists()
    shutil.copyfile(path,backup)
    payload=lambda x:{k:v for k,v in x.items() if k not in ('execution','metadata_correction')}
    digest=lambda x:hashlib.sha256(json.dumps(payload(x),sort_keys=True).encode()).hexdigest()
    numeric_hash=digest(data)
    data['execution'].update(backend='grace_slurm',slurm_job_id=job,output=str(path.parent))
    data['metadata_correction']=dict(original_artifact=backup.name,original_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
        numerical_payload_sha256=numeric_hash,reason='Shared local/remote verification runner hard-coded its backend label; actual execution was the recorded completed Slurm preflight.')
    assert digest(data)==numeric_hash
    temporary=path.with_suffix('.metadata.tmp')
    temporary.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    os.replace(temporary,path)
    print(json.dumps(dict(file=str(path),backend='grace_slurm',slurm_job_id=job,numerical_payload_unchanged=True)))
