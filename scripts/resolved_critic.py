"""Instrument the unchanged critic collector with return/noise moments."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dense_scaling as engine


def main(manifest,task_id,output):
    original=engine.pulse_chunk
    stats=dict(count=0,total=0.,squares=0.,delta_count=0,delta_total=0.,delta_squares=0.,previous=None)
    def instrument(*args):
        result=original(*args);values=result[2]
        stats["count"]+=len(values);stats["total"]+=float(values.sum());stats["squares"]+=float(values@values)
        if stats["previous"] is not None:
            delta=np.diff(np.concatenate(([stats["previous"]],values)))
        else:
            delta=np.diff(values)
        stats["delta_count"]+=len(delta);stats["delta_total"]+=float(delta.sum());stats["delta_squares"]+=float(delta@delta)
        stats["previous"]=float(values[-1])
        return result
    engine.pulse_chunk=instrument
    engine.run(manifest,task_id,output)
    path=Path(output)/f"task-{task_id:05d}.json";payload=json.loads(path.read_text())
    count=stats["count"];delta_count=stats["delta_count"]
    assert count==max(payload["task"]["budgets"])+1 and delta_count==count-1
    variance=stats["squares"]/count-(stats["total"]/count)**2
    delta_variance=stats["delta_squares"]/delta_count-(stats["delta_total"]/delta_count)**2
    assert variance>0 and delta_variance>0
    payload["diagnostics"]["return_moments"]=dict(return_count=count,return_mean=stats["total"]/count,return_variance=variance,
        adjacent_delta_count=delta_count,adjacent_delta_variance=delta_variance,
        note="Measured on the SAME unchanged policy trajectory; variance normalization is a diagnostic, not a learning step")
    payload["instrument_source_sha256"]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for row in payload["records"]:
        row["return_variance"]=variance;row["delta_variance"]=delta_variance
        if row["mode"]=="critic": row["noise_normalized_error_fro2"]=row["finite_error_fro2"]/delta_variance
    engine.atomic_json(path,payload)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--manifest",required=True);p.add_argument("--task-id",type=int,required=True);p.add_argument("--output",required=True)
    a=p.parse_args();main(a.manifest,a.task_id,a.output)
