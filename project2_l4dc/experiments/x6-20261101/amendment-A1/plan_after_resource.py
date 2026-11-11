"""Stdlib-only resource report/FORMAL cost proposal, never dispatches jobs."""
import argparse
import json
import math
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    assert not a.out.exists(),'Use a new resource-plan version.'
    rows=[]
    for index in range(8):
        folder=a.raw/'resource'/('task-'+str(index))
        done=json.loads((folder/'DONE.json').read_text())
        assert done['status']=='COMPLETE' and len(done['task']['cells'])==1
        spec=done['task']['cells'][0]
        receipt=json.loads((folder/(spec['family']+'-n'+str(spec['n']))/'receipt.json').read_text())
        assert receipt['timing_only'] and receipt['status']=='COMPLETE'
        assert receipt['spec']==spec and len(receipt['rows'])==(12 if spec['n']>=48 else 10)
        stein=[r for r in receipt['rows'] if r['algorithm']=='Stein']
        ce=[r for r in receipt['rows'] if r['algorithm']=='CE']
        rows.append(dict(spec,seconds=receipt['seconds'],max_rss_KiB=receipt['max_rss_KiB'],
                         setup_seconds=receipt['setup_seconds'],
                         stein_prefix_seconds=[r['elapsed_seconds'] for r in stein],
                         ce_prefix_seconds=[r['elapsed_seconds'] for r in ce]))
    eq=json.loads((a.raw/'resource/task-0/equivalence.json').read_text())
    assert eq['status']=='PASS_BITWISE' and len(eq['checks'])==8
    seconds=sum(r['seconds'] for r in rows)
    minutes=max(1,math.ceil((1.3*seconds+60)/60))
    assert minutes<=60,'A1 measured FORMAL request exceeds40 SU: report before submitting.'
    # Timing excludes compressed archive writing. Reserve margin; review the
    # measured plan before acceptance, and measure I/O separately if necessary.
    result=dict(status='RESOURCE_COMPLETE_FORMAL_PROPOSAL_NOT_SUBMITTED',rows=rows,
        bitwise_and_tolerance_equivalence=eq,base_bundle_seconds=seconds,
        proposed_formal_wall_minutes=minutes,formal_tasks=40,cpus=1,memory_MiB=2048,
        formal_requested_bound_SU=40*minutes/60,resource_requested_bound_SU=2.,
        report_reserve_SU=1.,total_X6a_requested_upper_SU=3.+40*minutes/60,
        timing_caveat='Resource timings exclude compressed artifact I/O; verify margin before formal.',
        required_next_gate='Claude X6a PILOT ACCEPTED; never infer approval from elapsed time.')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
