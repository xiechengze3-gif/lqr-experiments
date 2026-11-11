"""Recognize known X10b report IDs in the still-unsubmitted v3 queue preflight."""
import ast,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'submit_calibration_corrected_v3.py').read_text()
old="assert all(x[0].split('_')[0] in old for x in queue),'Unexpected own reservation; reconcile first.'"
new="""allowed=set(old)
report=BASE/'results/x10-20261106/X10b/submissions/REPORT_CHAIN_v1.json'
if report.exists():
    chain=json.loads(report.read_text());assert chain['status']=='REPORT_CHAIN_SUBMITTED' and len(chain['jobs'])==5
    allowed.update(x['job'] for x in chain['jobs'])
    for job in old:
        rows=[line.split('|') for line in call(['sacct','-X','--array','-n','-P','-j',job,'--format=JobID,State']).splitlines() if line]
        assert len(rows)==32 and all(x[1]=='COMPLETED' for x in rows)
assert all(x[0].split('_')[0] in allowed for x in queue),'Unexpected own reservation; reconcile first.'"""
assert s.count(old)==1;s=s.replace(old,new);ast.parse(s)
p=R/'submit_calibration_corrected_v3r2.py'
with p.open('xb') as f:f.write(s.encode())
digest=hashlib.sha256(p.read_bytes()).hexdigest()
runner=(R/'Submit-Calibration-v3.ps1').read_text()
runner=runner.replace('submit_calibration_corrected_v3.py','submit_calibration_corrected_v3r2.py').replace('CORRECTION_PREPARED_v3.json','CORRECTION_PREPARED_v3r2.json').replace('4fd476e7cad7ae398217e73cb904128078f7b9ab1ff773d12435a5e08abf8a6a',digest)
with (R/'Submit-Calibration-v3r2.ps1').open('xb') as f:f.write(runner.encode())
proof=dict(status='PREPARED_NOT_SUBMITTED_AWAITING_CLAUDE_V3',source_sha256=digest,
    old_source_sha256=hashlib.sha256((R/'submit_calibration_corrected_v3.py').read_bytes()).hexdigest(),
    only_additional_change='recognize five known X10b report IDs by immutable report chain; verify all256 formal tasks COMPLETED if report exists',
    requested_upper_SU=2.75,numerical_changes=0,new_simulated_transitions=0)
with (R/'CORRECTION_PREPARED_v3r2.json').open('x') as f:json.dump(proof,f,indent=2)
print(json.dumps(proof))
