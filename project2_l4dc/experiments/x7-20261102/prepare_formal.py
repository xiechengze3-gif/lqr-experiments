"""Resolve resources and model hashes after PILOT;no numerical/scientific retuning."""
import argparse
import hashlib
import json
import math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--resource-proof',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    assert not a.out.exists()
    config_path=ROOT/'config-protocol-v1.json';config=json.loads(config_path.read_text())
    proof=json.loads(a.resource_proof.read_text())
    assert proof['status']=='COMPLETE_RESOURCE_ONLY' and proof['zero_performance_readout']
    assert proof['config_sha256']==sha(config_path)
    for name,digest in config['scientific_sources'].items():assert sha(ROOT/name)==digest
    assert len(proof['cases'])==4 and len(proof['model_registry'])==32
    assert all(value==1. for value in proof['effective_billing_cores'])
    peak=max(row['maximum_RSS_KiB'] for row in proof['cases'])
    assert peak<=.8*2048*1024,'Memory headroom insufficient;report resource revision.'
    worst=sum(row['worst_full_path_seconds'] for row in proof['cases'])
    minutes=math.ceil((1.3*worst+60)/60)
    assert 1<=minutes<=20,'Measured task bound exceeds registered ceiling;report before scope/resource change.'
    formal_SU=32*minutes/60
    assert proof['requested_SU']+formal_SU+2<=15
    resolved=dict(config,stage='FORMAL',status='FORMAL_FROZEN',
        parent_protocol_config_sha256=sha(config_path),
        resource_complete_sha256=sha(a.resource_proof),
        model_registry=proof['model_registry'])
    plan=dict(experiment='X7',stage='FORMAL',tasks=32,concurrency=8,cpus=1,
        memory_MiB=2048,wall_minutes=minutes,requested_bound_SU=formal_SU,
        prior_requested_SU=proof['requested_SU'],reserved_report_SU=2,
        projected_cumulative_requested_SU=proof['requested_SU']+formal_SU+2,
        cap_requested_SU=15,automatic_retries=0,measured_case_worst_sum_seconds=worst,
        maximum_RSS_KiB=peak,formula='ceil((1.3*sum(case max full-path seconds)+60)/60)')
    a.out.mkdir(parents=True)
    target=a.out/'formal-config.json';target.write_text(json.dumps(resolved,indent=2)+'\n',encoding='utf-8')
    plan['formal_config_sha256']=sha(target)
    (a.out/'formal-plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='RESOLVED_AWAITING_EXPLICIT_FORMAL_ACCEPTED',plan=plan,
        config_sha256=sha(target),resource_proof_sha256=sha(a.resource_proof))))

if __name__=='__main__':main()
