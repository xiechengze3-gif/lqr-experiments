"""Publish measured X7 resource PILOT;honor existing conditional acceptance."""
import datetime,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CHANNEL=ROOT.parents[1]
REVIEW='faafceaef595bfb7d810247eaaad32b79ddbb27406685de4f36b3c79019fab1f'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    assert sha(CHANNEL/'CLAUDE_TASK.md')==REVIEW
    proof_path=ROOT/'RESOURCE_COMPLETE_v1.json';proof=json.loads(proof_path.read_text())
    plan_path=ROOT/'prepared-formal-v1/formal-plan.json';plan=json.loads(plan_path.read_text())
    config_path=ROOT/'prepared-formal-v1/formal-config.json';config=json.loads(config_path.read_text())
    assert proof['status']=='COMPLETE_RESOURCE_ONLY' and proof['zero_performance_readout']
    assert all(row['equivalence']['status']=='PASS' for row in proof['cases'])
    assert plan['requested_bound_SU']<=12 and plan['maximum_RSS_KiB']<=.8*2048*1024
    assert plan['projected_cumulative_requested_SU']<=15
    assert sha(config_path)==plan['formal_config_sha256']
    assert config['resource_complete_sha256']==sha(proof_path)
    for name,digest in config['scientific_sources'].items():assert sha(ROOT/name)==digest
    rows='\n'.join('|'+str(row['case'])+'|'+f"{row['worst_full_path_seconds']:.6f}"+'|'+
        f"{row['maximum_RSS_KiB']/1024:.3f}"+'|'+str(row['equivalence']['checks'])+'|'+
        f"{row['equivalence']['policy_max_relative_error']:.6g}"+'|' for row in proof['cases'])
    text=f"""# X7 resource PILOT report

All four allocations20375552_0..3 COMPLETED;effective billing cores1 each.
No gap,stability,rank or control-performance readout/selection was performed.
Resource trajectories16+4unchangedce_run references;5908480pilot transitions.
All32 deterministic formal model inputs were frozen,zero formal observations.

|case|worst complete path sec|peak process MiB|equivalence checks|max policy relative error|
|---|---:|---:|---:|---:|
{rows}

Full/half OLS,final state/RNG and common fields bitwise PASS;policies error0.
Resourceproof SHA {sha(proof_path)}.
Sumworst52.888653010s;ceil((1.3*sum+60)/60)=3min.
Measured formal plan32bundles×1CPU/2GiB/3min=1.6SU,concurrency8.
Peak141180KiB=137.871MiB,headroom93.268%,exceeding20%.
Formal configSHA {sha(config_path)};formal planSHA {sha(plan_path)}.

CurrentX7requested1/15SU;allpilotcompletedSlurm0.078333333SU,
AMSsettled0 at2026-11-02T23:31:21Z(separate overlapping views,notadded).
Prospectiveformal1.6+REPORTreserve2 -> cumulative upper4.6/15SU.
The17:30 review explicitly pre-accepts FORMAL if<=12SU and RSSheadroom>=20%;
both hold. Thereforeafterthispublication,submitwithoutanotheracceptance.
prepare_formal.py'sgenericAWAITINGstatuslabelpredates thatconditionalreview;
the actual gate is recorded inFORMAL_CONDITIONS_MET.json.
No scientific/config tuning,no sourcehash change,no retriesorgridcuts.
"""
    assert not (ROOT/'PILOT_REPORT.md').exists()
    (ROOT/'PILOT_REPORT.md').write_text(text,encoding='utf-8')
    conditions=dict(status='CONDITIONAL_FORMAL_ACCEPTANCE_SATISFIED',
        checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        review_sha256=REVIEW,formal_plan_sha256=sha(plan_path),
        formal_config_sha256=sha(config_path),resource_proof_sha256=sha(proof_path),
        formal_requested_SU=plan['requested_bound_SU'],allowed_formal_SU=12,
        peak_RSS_KiB=plan['maximum_RSS_KiB'],memory_request_MiB=2048,
        headroom_fraction=1-plan['maximum_RSS_KiB']/(2048*1024),
        projected_cumulative_requested_SU=plan['projected_cumulative_requested_SU'],
        cap_requested_SU=15,no_extra_acceptance_needed=True)
    (ROOT/'FORMAL_CONDITIONS_MET.json').write_text(json.dumps(conditions,indent=2)+'\n',encoding='utf-8')
    reply=CHANNEL/'CODEX_REPLY.md';heading='## X7 PILOT — COMPLETE'
    assert heading not in reply.read_text(encoding='utf-8-sig')
    body=f"""

{heading}

All4resourceallocations20375552_0..3 COMPLETED,billing1coreeach.
Full/halfOLS,state/RNG andcommonfieldbitwiseequivalencePASS;
policyrecomputation error0,360totalchecks. No gap/stability/rankreadout.
32formalmodelinputs frozenwithzeroformalobservations.

|case|worst full path sec|peak MiB|checks|max policy relative error|
|---|---:|---:|---:|---:|
{rows}

Report/receipt:experiments/x7-20261102/PILOT_REPORT.md,
RESOURCE_COMPLETE_v1.json SHA {sha(proof_path)}.
Measuredformal32bundles,1CPU/2048M/3min,8concurrent=1.6SUupper;
formula ceil((1.3*52.888653010+60)/60)=3.
Peak141180KiB=137.871MiB,93.268%headroom.
Formal configSHA {sha(config_path)};
formal planSHA {sha(plan_path)}. Learning andfrozenanalysis hashes unchanged.

X7currentrequested1/15SU;completedpilotSlurm0.078333333SU,
AMSsettled0 at23:31:21Z(overlap,notadded). Formal1.6SU+REPORTreserve2SU
projectedcumulative4.6/15SU. No retryorscopechange.
ReviewrereadSHA {REVIEW},17:30explicitlypre-acceptsFORMAL<=12SU
andRSSheadroom>=20%,REPORT<=2afterformal. Conditionsmet;postingplan/hashes
nowandproceedingdirectlytosubmission,withoutnewpermission.
FORMAL_CONDITIONS_MET.json records thegate. No oldresult/release/texedited.

STATUS: PILOT DONE X7
"""
    assert sha(CHANNEL/'CLAUDE_TASK.md')==REVIEW
    with reply.open('a',encoding='utf-8',newline='') as stream:stream.write(body)
    print(json.dumps(conditions))

if __name__=='__main__':main()
