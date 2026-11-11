"""Cheap oracle controls, excluded from all sampled algorithm comparisons."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dense_scaling import atomic_json,evaluate,targets
from direct_stein_final import correct,update
from final_round import make_system
from final_npg_audit import write_csv


def run(out):
    rows=[]
    for rank,tau in [(50,0.),(4,0.),(4,.03),(4,.1)]:
        for seed in (1001,1002):
            s=make_system(50,rank,seed,tau)
            for method in ('dense','forced_rank4'):
                k=s['K0'].copy()
                for stage in range(9):
                    q,p=evaluate(s,k)
                    rows.append(dict(rank=rank,tau=tau,system_seed=seed,method=method,stage=stage,
                        normalized_gap=q['gap']/s['initial_gap'] if q['gap'] is not None else None,
                        diagnostic_only=True,sampled_transitions=0,**q))
                    if p is None:break
                    truth=targets(s,k,16,p)
                    gg,zz,_=correct(truth['G'],truth['Z'],'dense' if method=='dense' else 'known_rank',known_rank=4)
                    k,_=update(k,s['R'],gg,zz,.25)
    out.mkdir(parents=True,exist_ok=True);write_csv(out/'population_controls.csv',rows)
    atomic_json(out/'population_controls.json',dict(rows=rows,sampled_transitions=0,
        interpretation='Oracle negative-control and tail diagnostics; not model-free performance.'))
    print([(r['rank'],r['tau'],r['system_seed'],r['method'],r['normalized_gap']) for r in rows if r['stage']==8])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
