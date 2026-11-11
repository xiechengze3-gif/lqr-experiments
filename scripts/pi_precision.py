"""Follow-up PI precision diagnostic, motivated by low-budget instability."""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dense_scaling import system,pulse_moments,pi_gain,evaluate,atomic_json,require_compute,rng_for


def main(manifest,task_id,out):
    require_compute()
    tasks=[t for t in json.loads(Path(manifest).read_text())["tasks"] if t["r"]==4]
    task=tasks[task_id];s=system(task);n=task["n"];count=256*n*n;records=[];start=time.time()
    for method in ("raw","truncated"):
        k=s["K0"].copy();x=np.zeros(n);total=0
        for stage in range(4):
            rng=rng_for(74491,n,task["system_seed"],stage)
            _,x,z,g,_,used=next(pulse_moments(s,k,x,[count],16,1.,rng,burn=1024));total+=used
            candidate,_,_=pi_gain(s,g,g@k-z,None if method=="raw" else 4)
            quality,_=evaluate(s,candidate)
            records.append(dict(method=method,stage=stage+1,N=count,transitions=total,**quality))
            atomic_json(Path(out)/f"progress-{task_id:02d}.json",dict(task=task,records=records,wall_seconds=time.time()-start))
            print(json.dumps(dict(task_id=task_id,method=method,stage=stage+1,N=count,transitions=total,**quality)),flush=True)
            if not quality["stable"]: break
            k=candidate
    atomic_json(Path(out)/f"precision-{task_id:02d}.json",dict(task=task,records=records,planned_stages=4,
        pulse_blocks_per_stage=count,wall_seconds=time.time()-start,slurm_job_id=os.environ["SLURM_JOB_ID"],
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        design="Exploratory phase II: larger fixed N=256*n^2 batches after phase-I instability; does not independently fit dimension exponents"))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--manifest",required=True);p.add_argument("--task-id",type=int,required=True);p.add_argument("--output",required=True)
    a=p.parse_args();main(a.manifest,a.task_id,a.output)
