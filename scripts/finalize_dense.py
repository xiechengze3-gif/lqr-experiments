"""Aggregate the completed precision follow-up and main study on Grace."""
import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np


def main(overview,precision,out):
    if not os.environ.get("SLURM_JOB_ID"): raise RuntimeError("Grace compute nodes only")
    overview,precision,out=Path(overview),Path(precision),Path(out);out.mkdir(parents=True,exist_ok=True)
    paths=sorted((precision/"raw").glob("precision-*.json"))
    if len(paths)!=8: raise RuntimeError("Missing precision task outputs")
    raw_rows=[];groups=defaultdict(list)
    for path in paths:
        data=json.loads(path.read_text());task=data["task"]
        lookup={(r["method"],r["stage"]):r for r in data["records"]}
        for method in ("raw","truncated"):
            for stage in range(1,5):
                row=dict(task_id=int(path.stem.split("-")[-1]),n=task["n"],r=4,tail=task["tail"],system_seed=task["system_seed"],method=method,stage=stage,
                         N=data["pulse_blocks_per_stage"],transitions=stage*(1024+(data["pulse_blocks_per_stage"]+1)*16),stable=False,gap=None,observed=False)
                if (method,stage) in lookup: row.update(lookup[method,stage],observed=True)
                raw_rows.append(row);groups[row["n"],row["tail"],method,stage].append(row)
    aggregates=[]
    for (n,tail,method,stage),rows in groups.items():
        gaps=[r["gap"] for r in rows if r.get("gap") is not None]
        aggregates.append(dict(n=n,tail=tail,method=method,stage=stage,expected=len(rows),
            stable_rate=float(np.mean([r["stable"] for r in rows])),transitions=rows[0]["transitions"],
            gap_mean_available=float(np.mean(gaps)) if gaps else None,
            gap_min_available=min(gaps) if gaps else None,gap_max_available=max(gaps) if gaps else None,
            success_gap1=float(np.mean([r["stable"] and r["gap"]<=1 for r in rows])),
            success_gap5=float(np.mean([r["stable"] and r["gap"]<=5 for r in rows]))))
    def write(name,rows):
        keys=list(dict.fromkeys(k for r in rows for k in r))
        with (out/name).open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    write("pi_precision_records.csv",raw_rows);write("pi_precision_aggregate.csv",aggregates)
    summary=dict(main_profiles={p:json.loads((overview/p/"report/summary.json").read_text()) for p in ("scaling","approximate","actor")},
        reference_tasks=len(list((overview/"references/raw").glob("reference-*.json"))),precision_tasks=len(paths),
        complexity=json.loads((overview/"report/derived_complexity.json").read_text()),pi_precision_final=[r for r in aggregates if r["stage"]==4],
        cautions=["Four system seeds for statistical fits, two for actor results", "PI precision batches selected after observing low-budget instability",
                  "Critic exponents are not end-to-end actor exponents", "PG uses scalar-normalized sampled nominal covariance", "m=n throughout"])
    (out/"combined_summary.json").write_text(json.dumps(summary,indent=2,allow_nan=False)+"\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(10,7))
    for i,n in enumerate((50,100)):
        for j,tail in enumerate((0.,.1)):
            ax=axes[i,j]
            for method,style,color in (("raw","--","#7e8187"),("truncated","-","#186b98")):
                data=sorted([r for r in aggregates if r["n"]==n and r["tail"]==tail and r["method"]==method],key=lambda r:r["stage"])
                data=[r for r in data if r["stable_rate"]==1 and r["expected"]==2]
                ax.loglog([r["transitions"] for r in data],[r["gap_mean_available"] for r in data],style+"o",color=color,label=method)
                if len(data)<4: ax.text(.05,.9-(method=="truncated")*.1,f"{method}: some outputs unstable",transform=ax.transAxes,fontsize=8)
            ax.axhline(1,color="black",alpha=.3,lw=.7)
            ax.set_title(f"Direct PI, n={n}, r=4, tail F={tail:g}")
            ax.set_xlabel("Primitive transitions")
            ax.set_ylabel("Absolute cost gap")
            ax.legend();ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/"pi_precision.png",dpi=160);plt.close(fig)
    print(json.dumps(summary),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--overview",required=True);p.add_argument("--precision",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();main(a.overview,a.precision,a.output)
