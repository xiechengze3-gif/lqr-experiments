"""Stdlib-only X7 freeze and PROTOCOL publication;never submits or simulates."""
import ast
import datetime
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CHANNEL=ROOT.parents[1]
GO_SHA='6542a46618bc7f2ba22bc985ca7ec8944266eea3e2b4ad70e09377457b16e58d'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    task=CHANNEL/'CLAUDE_TASK.md'
    assert sha(task)==GO_SHA,'Review changed;read before publishing.'
    names=['frozen_engine.py','ce_fullrank.py','analyze_ce.py','x7_driver.py']
    for name in names:ast.parse((ROOT/name).read_text(),filename=name)
    sources={name:sha(ROOT/name) for name in names}
    assert sources['frozen_engine.py']=='9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989'
    config=json.loads((ROOT/'CONFIG_DRAFT.json').read_text())
    config.update(stage='PROTOCOL',status='PROTOCOL_FROZEN',scientific_sources=sources)
    config_path=ROOT/'config-protocol-v1.json'
    assert not config_path.exists()
    config_path.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    science_table='\n'.join(f'|{name}|{digest}|' for name,digest in sources.items())
    protocol=(ROOT/'PROTOCOL_PLAN.md').read_text()+f"""

## Frozen source/config hashes

Config SHA256: {sha(config_path)}

|source|SHA256|
|---|---|
{science_table}

Local checks:AST parse and scalar grid/count/resource arithmetic only,PASS.
Numerical equivalence/timing/RSS are PENDING the approved compute-node PILOT.
Author GO snapshot SHA: {GO_SHA};preparation spent0SU.
"""
    protocol_path=ROOT/'PROTOCOL.md';assert not protocol_path.exists()
    protocol_path.write_text(protocol,encoding='utf-8')
    (ROOT/'CLAUDE_TASK_GO.md').write_bytes(task.read_bytes())
    hashes={name:sha(ROOT/name) for name in names+[
        'config-protocol-v1.json','PROTOCOL.md','PROTOCOL_PLAN.md','CLAUDE_TASK_GO.md']}
    digest_path=ROOT/'SHA256SUMS'
    assert not digest_path.exists()
    digest_path.write_text(''.join(f'{value}  {name}\n' for name,value in hashes.items()),encoding='utf-8')
    manifest=dict(status='PROTOCOL_FROZEN_WAITING_ACCEPTED',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        author_go_task_sha256=GO_SHA,config_sha256=sha(config_path),
        manifest_sha256=sha(digest_path),files=hashes,
        X7_requested_SU=0,X7_settled_SU=0,planning_upper_SU=1+32/3+2,
        simulations_run=False,numerical_equivalence='PENDING_COMPUTE_NODE_PILOT')
    (ROOT/'PROTOCOL_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    heading='## X7 PROTOCOL'
    reply=CHANNEL/'CODEX_REPLY.md'
    assert heading not in reply.read_text(encoding='utf-8-sig')
    body=f"""

{heading}

X7 GO reread;taskSHA {GO_SHA}. Protocol prepared before anyX7 numerical run.
Files:experiments/x7-20261102/PROTOCOL.md,config-protocol-v1.json,
frozen_engine.py,ce_fullrank.py,analyze_ce.py,x7_driver.py,SHA256SUMS and
PROTOCOL_MANIFEST.json. ConfigSHA {sha(config_path)};
SHA256SUMS SHA {sha(digest_path)}.

|source|SHA256|
|---|---|
{science_table}

Resolved design:Sfamily,n=m24/48,full-rank geometric.7^(j-1) and polynomial1/j,
independent Haar A/B streams,K0zero,Q/R/WI,nu1,burn512,p0class<=1.5625.
Formalids501-508 xseeds1801-1804;pilots9501/9502 x8101/8102,no selection.
N24=192/768/3072/12288/49152/196608,N48=384/1536/6144/24576/98304/393216.
Everyarmsharesoneunwhitenedfull-prefixOLS ononecontinuousCEtrajectory;
splitthreshold usesexacthalf-prefixsufficientstatistics.

Fixedk<n:n24=1/2/3/4/6/8/12/16;n48 additionally24/32;densek=n.
AdaptivepaperC5 EXACT2.569,delta.05;splitproxy norm(B1-B2,op)/2,strict>.
SensitivityC.5/1.0 labeledsensitivity,not selection. Note:X3'sarchivalunrounded
constantwas2.569143010355372;thisprotocolusesX7GO'sexplicitliteral2.569
without recalibration. Exposedhereforreviewbeforeanyrun.
13/15arms,768prefixfullOLSfits,10752outputs;128physicaltrajectories and
37814272formaltransitionsincludingburnonce,not a sumoverreusedarms/prefixes.

Frozen analysis:full32 failure-inclusiveabs/relativegapmedian/IQR andstable
counts;allfixed/adaptive/sensitivity dense/arm pairedratios underbothstable
andfailure-inclusivedefinitions,5000systemclusterBS withcommondrawsacross
N/arms/definitions/slopes. Emptyconditionalresamplesandinfquantilesretained.
Posthocbestfixedincludesdense(k=n),minFULL32medianabsgap,tieslowerk;
besttruncatedalsoseparate,neverper-trialtruthselection. Chosenordermedian/IQR
includesfailedoutputs;adaptive0retained. Slopesoflogfull32mediangapvslogN
overpredeclaredallsixandlastthree,NAonanyinf/nonpositivepoint;conditional
finite-bootstrapCIwithunidentifiedmass. Noenforcedmonotonicity/rate or
budget-to-epsilonclaimonthisfactor4grid. Alltau²/beta for k0..n.

PILOT proposedonlyAFTERyourPROTOCOLACCEPTED:4case tasks,each4pilotpaths
+1unchangedce_runreference,1CPU/2GiB/15min=1SUupper. Full/halfOLS,state/RNG
bitwise andcommonpolicies1e-11equivalence;runtime/RSSonly,no gap/stability/
rankreadout. All32formalmodelsfrozenwithoutformalobservations.
LocalAST andscalarcount/budgetchecksPASS;numericalequivalence/timingPENDING.

Formalplanningceiling32bundles x1CPU/2GiB/20min=10.666667SU;resolvedrequest
onlyaftermeasurement:ceil((1.3*sum4caseworstpathseconds+60)/60)min.
RSS>=20%headroomrequired. REPORTreserve2SU(4audits20min+summary40min).
TotalconservativeUNMEASUREDenvelope13.666667/15SU,automaticretries0.
Ifmeasuredlimit>20minorcost>15,reportbeforeanyformal,noautomaticgridcut.
PILOTreport/resolvedhashesandmeasuredformalplanwaitforexplicitFORMALACCEPTED.
OutputCSVsdirectlyatx7-20261102/;PNG/SVG,provenance/failuresincluded.

X7requested0/15SU,settled0SU;nojobsubmitted. IndependentX6finalrequested
343.366666667/400SU,completedSlurm242.363888889SU;AMS242.290277778SU
at14:43:51Z(overlap,notadded;historicalsnapshot,notcurrentaccountbalance).
AllnewstorageE/remoteX7,cachesexplicit,threads1,noinstallations. Nooldresults/
releases/papertexedited. Continuingforegroundreviewmonitoring;waitingfor
PROTOCOLACCEPTEDbeforePILOT.

STATUS: PROTOCOL DONE X7
"""
    assert sha(task)==GO_SHA
    with reply.open('a',encoding='utf-8',newline='') as stream:stream.write(body)
    print(json.dumps(manifest))

if __name__=='__main__':main()
