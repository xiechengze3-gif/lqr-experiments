"""Separate measured label variance from matrix estimation dimension."""
import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np


def main(report,out):
    if not os.environ.get("SLURM_JOB_ID"): raise RuntimeError("Grace compute nodes only")
    report,out=Path(report),Path(out);out.mkdir(parents=True,exist_ok=True)
    with (report/"records.csv").open(newline="",encoding="utf-8") as f: data=list(csv.DictReader(f))
    for row in data:
        for key in ("n","r","N","system_seed","finite_error_fro2","noise_normalized_error_fro2","delta_variance","return_variance"):
            if row.get(key): row[key]=float(row[key])
    fits=[]
    rng=np.random.default_rng(79939)
    def estimate(rows,metric,use_N=True):
        cluster=defaultdict(list)
        for r in rows: cluster[r["system_seed"]].append(r)
        names=sorted(cluster)
        def fit(values):
            x=np.array([[1,np.log(r["n"]),np.log(r["r"]),-np.log(r["N"])] if use_N else [1,np.log(r["n"]),np.log(r["r"])] for r in values])
            y=np.log([r[metric] for r in values]);c=np.linalg.lstsq(x,y,rcond=None)[0]
            return c,float(1-np.sum((y-x@c)**2)/np.sum((y-y.mean())**2))
        c,r2=fit(rows);boot=[]
        for _ in range(800):
            draw=rng.choice(names,len(names),replace=True)
            b,_=fit([r for seed in draw for r in cluster[seed]]);boot.append(b)
        ci=np.quantile(boot,[.025,.975],axis=0)
        return dict(alpha_n=float(c[1]),beta_r=float(c[2]),alpha_ci=ci[:,1].tolist(),beta_ci=ci[:,2].tolist(),
            gamma_N=float(c[3]) if use_N else None,gamma_ci=ci[:,3].tolist() if use_N else None,log_R2=r2,
            observations=len(rows),system_clusters=len(names),window="Exact rank, r/n<=.2, N/n=8192 or 32768")
    selected=[r for r in data if r["mode"]=="critic" and r["task_status"]=="complete" and r["r"]<=.2*r["n"]]
    for algorithm in ("Z","joint"):
        for method in ("raw","truncated"):
            rows=[r for r in selected if r["algorithm"]==algorithm and r["method"]==method]
            for metric in ("finite_error_fro2","noise_normalized_error_fro2"):
                fits.append(dict(algorithm=algorithm,method=method,metric=metric,**estimate(rows,metric)))
    unique={tuple(r[k] for k in ("n","r","system_seed")):r for r in selected}
    variance_fit=estimate(list(unique.values()),"delta_variance",use_N=False)
    summary=dict(fits=fits,measured_adjacent_return_variance_fit=variance_fit,
        interpretation="Dividing by measured adjacent-return variance diagnoses parameter-count dependence; unnormalized errors determine actual fixed-precision sample budgets. Normalized fits do NOT remove label noise from the algorithm.",
        noise_expected="Raw matrix degrees roughly n^2; rank-truncated degrees roughly rn. Label variance has an O(n) upper bound with fixed scalar constants, giving a possible extra n in worst-case upper bounds.",
        caution="Empirical scalar normalization does not fully remove heteroskedasticity or the dependence on Sigma; four system clusters and finite ranges only")
    (out/"noise_decomposition.json").write_text(json.dumps(summary,indent=2)+"\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(11,8))
    for j,algorithm in enumerate(("Z","joint")):
        for i,metric in enumerate(("finite_error_fro2","noise_normalized_error_fro2")):
            for n,color in ((50,"#12699c"),(100,"#ad4b2c")):
                for method,style in (("raw","--"),("truncated","-")):
                    grouped=defaultdict(list)
                    for r in data:
                        if r["mode"]=="critic" and r["algorithm"]==algorithm and r["method"]==method and r["n"]==n and r["N"]==32768*n:
                            grouped[r["r"]].append(r[metric])
                    ranks=sorted(grouped)
                    axes[i,j].loglog(ranks,[np.mean(grouped[r]) for r in ranks],style+"o",color=color,label=f"n={n}, {method}")
            axes[i,j].set_title(algorithm+(": error" if i==0 else ": error / measured label variance"))
            axes[i,j].set_xlabel("Rank r")
            axes[i,j].set_ylabel("Mean Frobenius error squared" if i==0 else "Variance-normalized error")
            axes[i,j].grid(alpha=.2);axes[i,j].legend(fontsize=7)
    fig.tight_layout();fig.savefig(out/"noise_decomposition.png",dpi=160);plt.close(fig)
    print(json.dumps(summary),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--report",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();main(a.report,a.output)
