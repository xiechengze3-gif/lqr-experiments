"""Prepare X12 adapters; preserve actor/summary math, never submit/execute."""
import ast,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent;X=R.parent/'x10-20261106';D=R/'runtime-prepared-v1';D.mkdir()
def put(name,s):
    with (D/name).open('xb') as f:f.write(s if isinstance(s,bytes) else s.encode())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
formal=(X/'prepared-actor-formal-v1/formal_driver.py').read_text()
assert formal.count('/results/x10-20261106/X10b')==1 and formal.count("experiment='X10b'")==1
formal=formal.replace('/results/x10-20261106/X10b','/results/x12-20261106').replace("experiment='X10b'","experiment='X12'")
ast.parse(formal);put('formal_driver.py',formal)
analysis=(X/'actor-report-src-v1/analyze_actor_five_rungs.py').read_text()
assert analysis.count('/results/x10-20261106/X10b')==1
analysis=analysis.replace('/results/x10-20261106/X10b','/results/x12-20261106')
ast.parse(analysis);put('analyze_actor.py',analysis)
put('paper_cross.py',(X/'actor-report-baseline-v1/paper_cross.py').read_bytes())
raw=(X/'actor-correction-controls-v2/raw_delivery_v2.py').read_text()
edits={
 '/results/x10-20261106/X10b':'/results/x12-20261106',
 '/tmp/x10-20261106':'/tmp/x12-20261106',
 'x10b-raw-':'x12-raw-',
 'X10B_RAW_SNAPSHOT':'X12_RAW_SNAPSHOT',
 "eq = OUT/'resource-v2/equivalence'":"eq = OUT/'calibration-resolution-v1'",
 "assert json.loads((eq/'PILOT_DONE.json').read_text())['status'] == 'PASS'":"assert json.loads((eq/'DONE.json').read_text())['status'] in ['PASS_CALIBRATION','RIGHT_CENSORED_STOP']",
 "[OUT/'resource-v1', eq]":"[OUT/'calibration-v1', eq, OUT/'failures', OUT/'submission-correction-v2']",
 "directory = OUT/'resource-v2'/algorithm":"directory = OUT/'timing-v1'/algorithm",
 "r'n(?:24|36|48|72)-new-five-(?:NPG|PI)'":"r'n60-nine-(?:NPG|PI)'"}
for a,b in edits.items():assert a in raw,a;raw=raw.replace(a,b)
ast.parse(raw);put('raw_delivery_v1.py',raw)
# All scalar/statistical routines remain literal identical to the X10b source.
def functions(s):return {n.name:ast.get_source_segment(s,n) for n in ast.parse(s).body if isinstance(n,ast.FunctionDef)}
oldfunctions=functions((X/'actor-report-src-v1/analyze_actor_five_rungs.py').read_text());newfunctions=functions(analysis)
assert oldfunctions==newfunctions
proof=dict(status='PREPARED_NOT_EXECUTED_NOT_SUBMITTED',formal_metadata_edits_only=True,
    analyzer_all_functions_literal_identity=True,summary_schema_exact_original=True,statistic_changes=0,
    raw_transfer_scope_adapted_to_X12=True,unpack_function_literal_identity=functions(raw)['unpack']==functions((X/'actor-correction-controls-v2/raw_delivery_v2.py').read_text())['unpack'].replace('X10B_RAW_SNAPSHOT','X12_RAW_SNAPSHOT'),
    files={p.name:sha(p) for p in D.iterdir() if p.is_file()},new_training_transitions=0)
assert proof['unpack_function_literal_identity']
with (D/'ADAPTER_SOURCE_PROOF.json').open('x') as f:json.dump(proof,f,indent=2)
print(json.dumps(proof))
