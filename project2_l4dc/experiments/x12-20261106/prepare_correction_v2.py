"""Prepare only; corrected submission remains gated on Claude review."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'submit_calibration_frozen_v1.py').read_text()
edits={
 "assert REL.is_dir() and not OUT.exists()":"""assert REL.is_dir() and OUT.is_dir()
assert not (OUT/'budget/LEDGER_v1.json').exists()
assert not (OUT/'calibration-v1').exists() and not (OUT/'calibration-resolution-v1').exists()
assert (OUT/'submissions/calibration-v1.BEGIN.json').exists()
assert not (OUT/'submissions/calibration-v1.json').exists()
assert not (OUT/'submissions/resolve-v1.BEGIN.json').exists()
assert not call(['squeue','-r','-h','-u','changze','-n','x12-calibration-v1,x12-resolve-v1,x12-calibration-v2,x12-resolve-v2','-o','%i']).strip()
assert not call(['sacct','-X','--array','-n','-P','-u','changze','-S','2026-11-06T00:00:00','--name=x12-calibration-v1,x12-resolve-v1,x12-calibration-v2,x12-resolve-v2','--format=JobID']).strip()
META=OUT/'submission-correction-v2'""",
 "OUT.mkdir();(OUT/'logs').mkdir();(OUT/'submissions').mkdir();(OUT/'budget').mkdir()":"META.mkdir()",
 "OUT/'submissions/BEFORE_CALIBRATION_v1.json'":"META/'BEFORE_CALIBRATION_v2.json'",
 "dest=OUT/'submissions'/(label+'.json')":"dest=META/(label+'.json')",
 "'--cpus-per-task=1'":"'--ntasks=1','--cpus-per-task=1'",
 "submit('calibration-v1'":"submit('calibration-v2'",
 "submit('resolve-v1'":"submit('resolve-v2'",
 "'--job-name=x12-calibration-v1'":"'--job-name=x12-calibration-v2'",
 "'--job-name=x12-resolve-v1'":"'--job-name=x12-resolve-v2'",
 "logs/calibration-v1-%A_%a.out":"logs/calibration-v2-%A_%a.out",
 "logs/resolve-v1-%j.out":"logs/resolve-v2-%j.out",
 "save(OUT/'budget/LEDGER_v1.json'":"save(OUT/'budget/LEDGER_v2.json'",
 "OUT/'submissions/AFTER_CALIBRATION_v1.json'":"META/'AFTER_CALIBRATION_v2.json'",
 "status='CALIBRATION_SUBMITTED_ONCE'":"status='CALIBRATION_SUBMITTED_ONCE_CORRECTED_METADATA_V2'"}
for a,b in edits.items():assert s.count(a)==1,a;s=s.replace(a,b)
compile(s,'submit_calibration_corrected_v2.py','exec')
p=R/'submit_calibration_corrected_v2.py'
with p.open('xb') as f:f.write(s.encode())
proof=dict(status='PREPARED_NOT_SUBMITTED_WAITING_CLAUDE',source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
    edits=edits,additional_resources_from_correction=0,calibration_request_SU=2.75,
    old_rejected_attempt_allocations=0,numerical_source_changes=0,old_files_untouched=True)
with (R/'CORRECTION_PREPARED_v2.json').open('x') as f:json.dump(proof,f,indent=2)
print(json.dumps({k:v for k,v in proof.items() if k!='edits'}))
