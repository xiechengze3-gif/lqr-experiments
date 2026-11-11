"""Prepare requested stale-dependency correction only; no submission."""
import ast,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'submit_calibration_corrected_v2.py').read_text()
old="assert len(states)==1 and states[0].split('|')[1] in ['RUNNING','COMPLETED','PENDING','COMPLETING']"
new="assert len(states)==1 and states[0].split('|')[1]=='COMPLETED', 'All8 predecessor completion must be proved.'"
assert s.count(old)==1;s=s.replace(old,new)
needle="META.mkdir()\naccount=call(['myproject'])"
replacement="""assert sum(x[0].split('_')[0]=='20416268' for x in queue)<=24
assert sum(x[1] in ['RUNNING','COMPLETING','CONFIGURING'] for x in queue)+8<=64
lane=['20416269','20416270','20416279','20416280','20416281','20416282']
ready=set()
for job in lane:
    queued=[x for x in queue if x[0].split('_')[0]==job]
    if not queued:continue
    assert len(queued)<=32
    raw=call(['scontrol','show','job','-o',job])
    import re
    records=[dict(re.findall(r'(\\S+?)=(\\S*)',line)) for line in raw.splitlines() if line.startswith('JobId=')]
    assert records and all(x['ArrayTaskThrottle']=='32' for x in records)
    for row in records:
        dependency=row['Dependency']
        if dependency=='(null)':ready.add(job)
        else:
            i=lane.index(job);assert i>0 and dependency.startswith('afterok:'+lane[i-1]+'_')
assert len(ready)<=1, 'OtherX10b lane is no longer serial: reconcile reservation.'
META.mkdir()
account=call(['myproject'])"""
assert s.count(needle)==1;s=s.replace(needle,replacement)
drop="    '--dependency=afterok:'+':'.join(predecessors),'--job-name=x12-calibration-v2',"
assert s.count(drop)==1;s=s.replace(drop,"    '--job-name=x12-calibration-v2',")
s=s.replace("dependency='afterok:'+':'.join(predecessors)","dependency=None,predecessors_completed_verified=predecessors")
# Existing v1/v2 outputs remain immutable; only new receipts/metadata names.
s=s.replace("META=OUT/'submission-correction-v2'","META=OUT/'submission-correction-v3'")
s=s.replace("'x12-calibration-v1,x12-resolve-v1,x12-calibration-v2,x12-resolve-v2'","'x12-calibration-v1,x12-resolve-v1,x12-calibration-v2,x12-resolve-v2,x12-calibration-v3,x12-resolve-v3'")
s=s.replace("'--name=x12-calibration-v1,x12-resolve-v1,x12-calibration-v2,x12-resolve-v2'","'--name=x12-calibration-v1,x12-resolve-v1,x12-calibration-v2,x12-resolve-v2,x12-calibration-v3,x12-resolve-v3'")
for a,b in [('BEFORE_CALIBRATION_v2','BEFORE_CALIBRATION_v3'),('AFTER_CALIBRATION_v2','AFTER_CALIBRATION_v3'),("submit('calibration-v2'","submit('calibration-v3'"),("submit('resolve-v2'","submit('resolve-v3'"),
    ('--job-name=x12-calibration-v2','--job-name=x12-calibration-v3'),('--job-name=x12-resolve-v2','--job-name=x12-resolve-v3'),
    ('logs/calibration-v2-','logs/calibration-v3-'),('logs/resolve-v2-','logs/resolve-v3-'),('save(OUT/\'budget/LEDGER_v2.json\'','save(OUT/\'budget/LEDGER_v3.json\''),
    ('CALIBRATION_SUBMITTED_ONCE_CORRECTED_METADATA_V2','CALIBRATION_SUBMITTED_ONCE_SATISFIED_DEPENDENCY_V3')]:
    assert a in s,a;s=s.replace(a,b)
# Refuse rerun of the earlier rejected helpers, which never allocated a job.
needle="assert not (OUT/'submissions/resolve-v1.BEGIN.json').exists()"
insert=needle+"\nassert (OUT/'submission-correction-v2/calibration-v2.BEGIN.json').exists()\nassert not (OUT/'submission-correction-v2/calibration-v2.json').exists()\nassert not (OUT/'budget/LEDGER_v2.json').exists()"
assert s.count(needle)==1;s=s.replace(needle,insert)
ast.parse(s)
p=R/'submit_calibration_corrected_v3.py'
with p.open('xb') as f:f.write(s.encode())
proof=dict(status='PREPARED_NOT_SUBMITTED_AWAITING_CLAUDE_V3',source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
    requested_upper_SU=2.75,numerical_changes=0,changes='all8completed checks + current/global/persistent lane reservation; omit satisfied obsolete first8 dependency only; new metadata namespace')
with (R/'CORRECTION_PREPARED_v3.json').open('x') as f:json.dump(proof,f,indent=2)
print(json.dumps(proof))
