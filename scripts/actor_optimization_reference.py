"""Match actor iteration counts with noise-free updates; diagnostic only."""
import argparse
import csv
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dense_scaling import system,targets,trunc,pi_gain,eta,op,evaluate,require_compute
from scipy.linalg import solve_discrete_lyapunov


def main(manifest,out):
    require_compute();rows=[]
    for task_id,task in enumerate(json.loads(Path(manifest).read_text())["tasks"]):
        s=system(task)
        for algorithm in ("NPG","PG","PI"):
            for method in ("raw","truncated"):
                k=s["K0"].copy()
                for step in range(task["stages"]):
                    true=targets(s,k,task["horizon"])
                    z=true["Z"] if method=="raw" else trunc(true["Z"],task["r"])
                    if algorithm=="PI": nxt,_,_=pi_gain(s,true["G"],true["C"],None if method=="raw" else task["r"])
                    else:
                        direction=s["R"]@k+z
                        if algorithm=="PG":
                            covariance=solve_discrete_lyapunov(s["A"]-s["B"]@k,s["W"])
                            direction=direction@covariance/op(covariance)
                        nxt=k-eta(s)*direction
                    k=nxt;quality,_=evaluate(s,k)
                    rows.append(dict(task_id=task_id,n=task["n"],r=task["r"],tail=task["tail"],system_seed=task["system_seed"],
                        algorithm=algorithm,method=method,stage=step+1,reference_only=True,**quality))
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps([r for r in rows if r["stage"]==24]),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--manifest",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();main(a.manifest,a.output)
