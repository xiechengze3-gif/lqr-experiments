"""Post-study interpretation and plots. All numerical work requires Slurm."""
import argparse
import csv
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np


def read(path):
    with Path(path).open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))


def numeric(rows):
    for row in rows:
        for key,value in list(row.items()):
            if value in ("True","False"): row[key]=value=="True"
            elif value=="": row[key]=None
            else:
                try: row[key]=float(value)
                except (ValueError,TypeError): pass
    return rows


def write(path,rows):
    if not rows: return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open("w",newline="",encoding="utf-8") as f:
        out=csv.DictWriter(f,fieldnames=keys);out.writeheader();out.writerows(rows)


def main(root,out):
    if not os.environ.get("SLURM_JOB_ID"): raise RuntimeError("Grace compute nodes only")
    root,out=Path(root),Path(out);out.mkdir(parents=True,exist_ok=True)
    profiles={profile:numeric(read(root/profile/"report/records.csv")) for profile in ("scaling","approximate","actor")}
    source_hashes={profile:hashlib.sha256((root/profile/"report/records.csv").read_bytes()).hexdigest() for profile in profiles}
    results=[]
    rng=np.random.default_rng(626181)
    for algorithm,mode,metric in (("CE","ce","gap"),("Z","critic","finite_error_fro2"),("joint","critic","finite_error_fro2")):
        for method in ("raw","truncated"):
            rows=[r for r in profiles["scaling"] if r["algorithm"]==algorithm and r["mode"]==mode and r["method"]==method
                  and r["r"]<=.2*r["n"] and r["N"]>=128*r["n"]]
            groups=defaultdict(list)
            for row in rows: groups[(row["n"],row["r"],row["N"])].append(row)
            selected=[r for values in groups.values() if all(r["task_status"]=="complete" and r["observed"] for r in values)
                      and (mode!="ce" or all(r["stable"] for r in values)) for r in values if r.get(metric) and r[metric]>1e-14]
            clusters=defaultdict(list)
            for row in selected: clusters[row["system_seed"]].append(row)
            names=sorted(clusters)
            if len(names)<3: continue
            def fit(values):
                x=np.array([[1.,np.log(r["n"]),np.log(r["r"]),-np.log(r["N"])] for r in values])
                y=np.log([r[metric] for r in values]);c=np.linalg.lstsq(x,y,rcond=None)[0]
                return c,np.array([c[1]/c[3],c[2]/c[3],1/c[3]]) if c[3]>.1 else np.full(3,np.nan)
            coefficient,derived=fit(selected)
            boot=[]
            for _ in range(800):
                draw=rng.choice(names,len(names),replace=True)
                _,d=fit([r for name in draw for r in clusters[name]])
                if np.all(np.isfinite(d)): boot.append(d)
            ci=np.quantile(boot,[.025,.975],axis=0)
            results.append(dict(algorithm=algorithm,method=method,metric=metric,
                alpha_error=float(coefficient[1]),beta_error=float(coefficient[2]),gamma_error=float(coefficient[3]),
                n_sample_exponent=float(derived[0]),r_sample_exponent=float(derived[1]),epsilon_sample_exponent=float(derived[2]),
                n_sample_ci=ci[:,0].tolist(),r_sample_ci=ci[:,1].tolist(),epsilon_sample_ci=ci[:,2].tolist(),
                interpretation="Derived fixed-error statistical budget N ~ n^(alpha/gamma) r^(beta/gamma) epsilon^(-1/gamma); critic fits do not establish full actor sample complexity",
                uncertainty="Four shared system-seed clusters; bootstrap intervals omit model misspecification"))
    (out/"derived_complexity.json").write_text(json.dumps(results,indent=2,allow_nan=False)+"\n")
    pairs=[]
    for profile,rows in profiles.items():
        lookup={tuple(r.get(k) for k in ("task_id","mode","algorithm","stage","N","method")):r for r in rows}
        for row in rows:
            if row["method"]!="truncated": continue
            key=tuple(row.get(k) for k in ("task_id","mode","algorithm","stage","N"))+("raw",)
            raw=lookup.get(key)
            if not raw: continue
            pair={k:row.get(k) for k in ("n","r","tail","tail_shape","system_seed","trial_seed","mode","algorithm","stage","N","transitions")}
            pair.update(profile=profile,raw_stable=raw.get("stable"),truncated_stable=row.get("stable"))
            for metric in ("gap","finite_error_fro2"):
                if raw.get(metric) is not None and row.get(metric) is not None:
                    pair["raw_"+metric]=raw[metric];pair["truncated_"+metric]=row[metric]
                    if raw[metric]>1e-14: pair[metric+"_ratio"]=row[metric]/raw[metric]
            pairs.append(pair)
    write(out/"paired_comparisons.csv",pairs)
    references=[]
    for path in sorted((root/"references/raw").glob("reference-*.json")):
        data=json.loads(path.read_text())
        references.extend(dict(data["task"],**r) for r in data["records"])
    write(out/"converged_references.csv",references)
    (out/"provenance.json").write_text(json.dumps(dict(source_hashes=source_hashes,slurm_job_id=os.environ["SLURM_JOB_ID"],
        analysis_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+"\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,3,figsize=(14,8),sharex="col")
    for i,n in enumerate((50,100)):
        for j,algorithm in enumerate(("NPG","PG","PI")):
            ax=axes[i,j]
            for tail,color in ((0.,"#12699c"),(.1,"#ad4b2c")):
                for method,style in (("raw","--"),("truncated","-")):
                    data=[r for r in profiles["actor"] if r["n"]==n and r["r"]==4 and r["tail"]==tail and r["algorithm"]==algorithm and r["method"]==method]
                    grouped=defaultdict(list)
                    for r in data: grouped[r["stage"]].append(r)
                    stages=sorted(grouped)
                    # Require all planned replicates stable; do not plot survivor-only means.
                    available=[s for s in stages if all(r["stable"] and r.get("gap") is not None for r in grouped[s])]
                    ax.loglog([grouped[s][0]["transitions"] for s in available],[np.mean([r["gap"] for r in grouped[s]]) for s in available],
                              style+"o",color=color,markersize=3,label=f"tail F={tail:g}, {method}")
                    failed=sum(not r["stable"] for r in data if r["stage"]==1)
                    if failed: ax.text(.02,.94-.09*(2*(tail>0)+(method=="truncated")),f"{tail:g} {method}: {failed}/2 unstable at stage 1",transform=ax.transAxes,fontsize=7,color=color)
            ax.set_title(f"{algorithm}, n={n}, r=4")
            ax.set_ylabel("Absolute cost gap")
            ax.set_xlabel("Primitive transitions")
            ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(out/"actor_comparison.png",dpi=160);plt.close(fig)
    if references:
        fig,axes=plt.subplots(1,3,figsize=(13,4))
        floor_slopes=[]
        for ax,algorithm in zip(axes,("NPG","PG","PI")):
            for n,color in ((50,"#12699c"),(100,"#ad4b2c")):
                data=[r for r in references if r["n"]==n and r["algorithm"]==algorithm and r["method"]=="truncated"
                      and r["tail_shape"]=="energy" and r["tail"]>0 and r["converged"] and r["stable"]]
                grouped=defaultdict(list)
                for r in data: grouped[r["tail"]].append(r["gap"])
                levels=sorted(grouped)
                ax.loglog([v*v for v in levels],[np.mean(grouped[v]) for v in levels],"o-",color=color,label=f"n={n}")
                if len(levels)>2:
                    coefficients=np.polyfit(np.log([r["tail"]**2 for r in data]),np.log([r["gap"] for r in data]),1)
                    floor_slopes.append(dict(algorithm=algorithm,n=n,tail_energy_exponent=float(coefficients[0]),
                        intercept=float(coefficients[1]),converged_replicates=len(data),expected_replicates=16))
            ax.set_title(f"{algorithm}: converged noiseless reference")
            ax.set_xlabel("Frobenius tail energy squared")
            ax.set_ylabel("Absolute cost gap")
            ax.grid(alpha=.2);ax.legend()
        fig.tight_layout();fig.savefig(out/"converged_tail_floors.png",dpi=160);plt.close(fig)
        write(out/"tail_energy_slopes.csv",floor_slopes)
    print(json.dumps(results),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--root",required=True);parser.add_argument("--output",required=True)
    args=parser.parse_args();main(args.root,args.output)
