"""Converged tail references; this explicitly uses exact model derivatives."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.linalg import solve_discrete_lyapunov

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dense_scaling import system,targets,trunc,pi_gain,eta,op,evaluate,atomic_json,require_compute


def run(manifest,task_id,output):
    require_compute()
    tasks=[t for t in json.loads(Path(manifest).read_text())["tasks"] if t["mode"]=="deterministic"]
    task=tasks[task_id];s=system(task);records=[]
    for algorithm in ("NPG","PG","PI"):
        for method in ("raw","truncated"):
            k=s["K0"].copy();converged=False
            for step in range(8192):
                t=targets(s,k,task["horizon"])
                z=t["Z"] if method=="raw" else trunc(t["Z"],task["r"])
                if algorithm=="PI":
                    nxt,_,_=pi_gain(s,t["G"],t["C"],None if method=="raw" else task["r"])
                else:
                    direction=s["R"]@k+z
                    if algorithm=="PG":
                        covariance=solve_discrete_lyapunov(s["A"]-s["B"]@k,s["W"])
                        direction=direction@covariance/op(covariance)
                    nxt=k-eta(s)*direction
                change=op(nxt-k);k=nxt
                if change<1e-9:
                    converged=True;break
            quality,_=evaluate(s,k)
            records.append(dict(algorithm=algorithm,method=method,iterations=step+1,converged=converged,
                last_change_op=change,**quality))
    path=Path(output)/f"reference-{task_id:03d}.json"
    if path.exists(): raise RuntimeError("Refuse overwrite")
    atomic_json(path,dict(task=task,reference_only=True,stopping="operator norm of policy change <1e-9, at most 8192 iterations",records=records))
    print(json.dumps(dict(task_id=task_id,task=task,records=records)),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--manifest",required=True);p.add_argument("--task-id",type=int,required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.manifest,a.task_id,a.output)
