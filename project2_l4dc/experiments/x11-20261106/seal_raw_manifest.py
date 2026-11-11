"""Checksum all completed local raw files; no numerical processing."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent
assert json.loads((R/'REPORT_DONE_v1.json').read_text())['status']=='REPORT_COMPLETE'
files=[]
for prefix in ['pilot-v1','formal-v1']:
    for p in sorted((R/prefix).rglob('*')):
        if p.is_file():files.append(dict(path=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
assert sum(x['path'].startswith('formal-v1/') and x['path'].endswith('/DONE.json') for x in files)==352
assert sum(x['path'].startswith('formal-v1/') and '/fit-' in x['path'] and x['path'].endswith('.npz') for x in files)==1760
assert sum(x['path'].startswith('formal-v1/') and x['path'].endswith('/model.npz') for x in files)==352
with (R/'RAW_FILE_MANIFEST_v1.json').open('x') as f:json.dump(dict(status='SEALED_ALL_NEW_LOCAL_PILOT_FORMAL_RAW',files=files,
    total_files=len(files),bytes=sum(x['bytes'] for x in files),numerical_reanalysis=False,new_transitions=0),f,indent=2)
print(json.dumps(dict(status='SEALED',files=len(files),bytes=sum(x['bytes'] for x in files),new_transitions=0)))
