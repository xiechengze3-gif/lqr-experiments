"""Diagnose hard-SVD bias using the subspace exposed by the OLD stabilizer."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dense_scaling import system,nominal_covariance,pulse_moments,rng_for,eta,op,evaluate,atomic_json,require_compute


def main(manifest,task_id,out):
    require_compute()
    tasks=[t for t in json.loads(Path(manifest).read_text())["tasks"] if t["r"]==4 and t["tail"]==0]
    task=tasks[task_id];s=system(task)
    # This uses only a supplied matrix, but works because this specific OLD
    # generator leaked the true input space. It has no generic guarantee.
    u=np.linalg.svd(s["K0"],full_matrices=False)[0][:,:4];records=[]
    for algorithm in ("NPG","PG"):
        k=s["K0"].copy();x=np.zeros(task["n"]);total=0
        for stage,count in enumerate(task["batch_schedule"]):
            covariance=None
            if algorithm=="PG":
                x,covariance=nominal_covariance(s,k,x,32*task["n"],512,rng_for(4111,task["n"],task["system_seed"],0,stage))
                total+=32*task["n"]+512
            _,x,z,_,_,used=next(pulse_moments(s,k,x,[count],16,1.,rng_for(99111,task["n"],task["system_seed"],0,stage),burn=1024))
            total+=used;z=u@(u.T@z);direction=s["R"]@k+z
            if algorithm=="PG": direction=direction@covariance/op(covariance)
            k=k-eta(s)*direction;quality,_=evaluate(s,k)
            records.append(dict(algorithm=algorithm,method="K0_projector_diagnostic",stage=stage+1,N=count,transitions=total,**quality))
            if not quality["stable"]: break
    atomic_json(Path(out)/f"projector-{task_id:02d}.json",dict(task=task,records=records,slurm_job_id=os.environ["SLURM_JOB_ID"],
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        note="Benchmark-specific diagnostic: projector comes from leading K0 singular vectors. This geometry is unavailable from the new equal-singular-value K0; not a generic implementable guarantee."))
    print(json.dumps(dict(task=task,finals=[r for r in records if r["stage"]==24])),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--manifest",required=True);p.add_argument("--task-id",type=int,required=True);p.add_argument("--output",required=True)
    a=p.parse_args();main(a.manifest,a.task_id,a.output)
