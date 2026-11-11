"""Two-step diagnostic on the actual old failed systems, no retuning."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from dense_scaling import atomic_json,rng_for
from final_round import collect,quality
from direct_stein_final import correct,update
from final_npg_audit import write_csv


def run(out):
    old=Path('E:/ChatGPT/Results/LQR_experiments/adaptive50-20261012')
    out.mkdir(parents=True,exist_ok=True);allrows=[];total=0;endpoints=[]
    for tid in range(4):
        historical=json.loads((old/'DIRECT_PI/raw'/f'task-{tid:03d}.json').read_text());task=historical['task']
        with np.load(old/'systems'/f'system-{tid:03d}.npz') as d:s={k:d[k].copy() for k in d.files}
        for method in ('dense','known_rank','adaptive'):
            k=s['K0'].copy();x=np.zeros(50);status='completed';used_total=0;rows=[]
            for stage in (1,2):
                used=1024+65537*16;counted=False
                try:
                    x,(g,z,critic),halves,actual=collect(s,k,x,65536,
                        rng_for(202610123,50,task['system_seed'],task['policy_seed'],task['trial_seed'],stage),burn=1024)
                    assert actual==used;total+=used;used_total+=used;counted=True
                    gg,zz,info=correct(g,z,method,halves,4 if method=='known_rank' else None)
                    k,solve=update(k,s['R'],gg,zz,.25);q,_=quality(s,k)
                    if not q['stable']:status='controller_instability'
                    rows.append(dict(task=tid,method=method,stage=stage,eta=.25,blocks=65536,
                        transitions=used_total,diagnostic_only=True,**q,**critic,**solve,**info))
                except (np.linalg.LinAlgError,ValueError,ArithmeticError) as e:
                    if not counted:total+=used;used_total+=used
                    status='numerical_failure';rows.append(dict(task=tid,method=method,stage=stage,
                        eta=.25,blocks=65536,transitions=used_total,diagnostic_only=True,
                        normalized_gap=None,stable=None,failure=status,detail=str(e)))
                if status!='completed':break
            atomic_json(out/f'task-{tid}-{method}.json',dict(task=task,method=method,
                status=status,rows=rows,actual_transitions=used_total,diagnostic_only=True))
            np.savez(out/f'task-{tid}-{method}.npz',K=k,x=x)
            allrows+=rows;endpoints.append(dict(task=tid,method=method,status=status,
                final_g=rows[-1]['normalized_gap'],steps=len(rows),actual_transitions=used_total))
    write_csv(out/'rows.csv',allrows)
    atomic_json(out/'summary.json',dict(endpoints=endpoints,rows=allrows,
        actual_transitions=total,diagnostic_only=True,
        limitation='Two steps test the original failure point, not eight-step success or independent-system replication.'))
    print(json.dumps(dict(endpoints=endpoints,actual_transitions=total)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
