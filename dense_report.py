"""Dense-study rates, censored thresholds and tail diagnostics; Slurm only."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from dense_scaling import atomic_json, require_compute

FIELDS=["family","n","m","r","tail","tail_shape"]


def csv_write(path,rows):
    if not rows: return
    columns=list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(rows)


def expected(task):
    n,h=task["n"],task["horizon"]
    if task["mode"]=="actor":
        for algorithm in ("NPG","PG","PI"):
            used=0
            stages=task["stages"] if algorithm!="PI" else min(task["stages"],12)
            for stage in range(stages):
                count=task["batch_schedule"][stage]
                used+=1024+(count+1)*h+(32*n+512 if algorithm=="PG" else 0)
                for method in ("raw","truncated"):
                    yield "actor",algorithm,method,stage+1,count,used
    elif task["mode"]=="ce":
        for count in task["budgets"]:
            for method in ("raw","truncated"):
                yield "ce","CE",method,None,count,count+512
    elif task["mode"]=="critic":
        for count in task["budgets"]:
            used=1024+32*n+(count+1)*h
            for method in ("raw","truncated"):
                for mode,alg in (("critic","Z"),("critic","joint"),("one_step","NPG"),("one_step","PG"),("one_step","PI")):
                    yield mode,alg,method,None,count,used


def bootstrap_rate(rows,metric,draws=1000):
    clusters=defaultdict(list)
    for row in rows:
        if row.get(metric) is not None and row[metric]>0:
            clusters[row["system_seed"]].append(row)
    names=sorted(clusters)
    if len(names)<3: return dict(identified=False,reason="Fewer than three independent system-seed clusters")
    def design(values):
        x=np.array([[1.,np.log(r["n"]),np.log(r["r"]),-np.log(r["N"])] for r in values])
        y=np.log([r[metric] for r in values])
        return x,y
    x,y=design([r for values in clusters.values() for r in values])
    if np.linalg.matrix_rank(x)<4:
        return dict(identified=False,reason="Dimension/rank/sample design is not full rank")
    coef=np.linalg.lstsq(x,y,rcond=None)[0]
    fitted=x@coef
    rng=np.random.default_rng(952381)
    draws_coef=[]
    for _ in range(draws):
        selected=rng.choice(names,len(names),replace=True)
        values=[r for name in selected for r in clusters[name]]
        xx,yy=design(values)
        if np.linalg.matrix_rank(xx)==4:
            draws_coef.append(np.linalg.lstsq(xx,yy,rcond=None)[0])
    interval=np.quantile(np.asarray(draws_coef),[.025,.975],axis=0)
    return dict(identified=True,metric=metric,model="metric=C*n^alpha*r^beta/N^gamma",observations=len(y),
        system_seed_clusters=len(names),intercept=float(coef[0]),alpha_n=float(coef[1]),beta_r=float(coef[2]),gamma_N=float(coef[3]),
        alpha_ci=interval[:,1].tolist(),beta_ci=interval[:,2].tolist(),gamma_ci=interval[:,3].tolist(),
        log_R2=float(1-np.sum((y-fitted)**2)/np.sum((y-y.mean())**2)),
        uncertainty="Resample shared system-seed clusters across the whole grid; only four clusters, limited precision")


def run(manifest_path,raw_path,output_path):
    require_compute()
    data=Path(manifest_path).read_bytes(); manifest=json.loads(data)
    sha=hashlib.sha256(data).hexdigest()
    output=Path(output_path);output.mkdir(parents=True,exist_ok=True)
    rows,status,diagnostics=[],[],[]
    for task_id,task in enumerate(manifest["tasks"]):
        path=Path(raw_path)/f"task-{task_id:05d}.json"
        payload=json.loads(path.read_text()) if path.exists() else None
        if payload and (payload["task"]!=task or payload["manifest_sha256"]!=sha):
            raise RuntimeError("Manifest/source result mismatch")
        state=payload["status"] if payload else "missing"
        status.append(dict(task_id=task_id,status=state,mode=task["mode"],n=task["n"],r=task["r"]))
        if payload and payload.get("diagnostics"):
            diagnostics.append(dict(task_id=task_id,task=task,diagnostics=payload["diagnostics"],wall_seconds=payload["wall_seconds"]))
        base=dict(task_id=task_id,**{k:task[k] for k in FIELDS},system_seed=task["system_seed"],trial_seed=task["trial_seed"],task_status=state)
        actual=payload.get("records",[]) if payload else []
        if task["mode"]=="deterministic":
            rows.extend(dict(base,observed=True,**row) for row in actual)
            continue
        lookup={(r["mode"],r["algorithm"],r["method"],r.get("stage"),r["N"]):r for r in actual}
        for mode,alg,method,stage,count,transitions in expected(task):
            row=dict(base,mode=mode,algorithm=alg,method=method,stage=stage,N=count,transitions=transitions,
                     stable=False,gap=None,observed=False)
            found=lookup.get((mode,alg,method,stage,count))
            if found:
                if found["transitions"]!=transitions: raise RuntimeError("Primitive count mismatch")
                row.update(found,observed=True)
            elif state=="complete" and task["mode"]!="actor":
                raise RuntimeError("Complete task missing a planned prefix")
            rows.append(row)
    csv_write(output/"records.csv",rows);csv_write(output/"task_status.csv",status)
    atomic_json(output/"diagnostics.json",diagnostics)
    groups=defaultdict(list)
    for row in rows:
        if row["mode"] in ("floor_reference","deterministic"): continue
        key=tuple(row[k] for k in FIELDS)+(row["mode"],row["algorithm"],row["method"],row.get("stage"),row["N"],row["transitions"])
        groups[key].append(row)
    aggregates,success=[],[]
    group_fields=FIELDS+["mode","algorithm","method","stage","N","transitions"]
    for key,values in groups.items():
        info=dict(zip(group_fields,key),expected=len(values),observed=sum(r["observed"] for r in values),
                  complete=sum(r["task_status"]=="complete" for r in values),stable_rate=float(np.mean([r["stable"] for r in values])))
        for metric in ("gap","error_fro2","error_op","finite_error_fro2","update_error_fro2","residual_error_fro2"):
            available=[r[metric] for r in values if r.get(metric) is not None]
            if available:
                info[metric+"_mean_available"]=float(np.mean(available))
                info[metric+"_median_available"]=float(np.median(available))
                info[metric+"_count"]=len(available)
        aggregates.append(info)
        if info["mode"]=="critic": continue
        for epsilon in manifest["absolute_epsilons"]:
            good=[r["stable"] and r.get("gap") is not None and r["gap"]<=epsilon for r in values]
            success.append(dict(info,epsilon=epsilon,success_rate=float(np.mean(good))))
    csv_write(output/"aggregate.csv",aggregates);csv_write(output/"success_rates.csv",success)
    curves=defaultdict(list)
    for row in success:
        key=tuple(row[k] for k in FIELDS)+(row["mode"],row["algorithm"],row["method"],row["epsilon"])
        curves[key].append(row)
    thresholds=[]
    for key,values in curves.items():
        values.sort(key=lambda r:r["transitions"])
        complete=all(r["complete"]==r["expected"] for r in values)
        hits=[r for r in values if r["success_rate"]>=manifest["target_success"]] if complete else []
        sustained=None
        for i,row in enumerate(values):
            if complete and all(r["success_rate"]>=manifest["target_success"] for r in values[i:]):
                sustained=row["transitions"];break
        thresholds.append(dict(zip(FIELDS+["mode","algorithm","method","epsilon"],key),
            first_pointwise_success=hits[0]["transitions"] if hits else None,sustained_success=sustained,
            censored=not hits,maximum_tested_transitions=values[-1]["transitions"],complete=complete))
    csv_write(output/"thresholds.csv",thresholds)
    floors=[r for r in rows if r["mode"]=="floor_reference"]
    csv_write(output/"noiseless_references.csv",floors)
    # Fits concern exact-rank, low-r/n cases. Never silently fit survivor-only CE.
    fits=[]
    for alg,mode,metric in (("CE","ce","gap"),("Z","critic","finite_error_fro2"),("joint","critic","finite_error_fro2")):
        for method in ("raw","truncated"):
            eligible=[]
            for key,values in groups.items():
                prototype=values[0]
                if (prototype["family"]!="coupled_unstable" or prototype["tail"]!=0 or prototype["mode"]!=mode
                    or prototype["algorithm"]!=alg or prototype["method"]!=method
                    or prototype["r"]>prototype["n"]*.2 or prototype["N"]<128*prototype["n"]): continue
                if any(r["task_status"]!="complete" or not r["observed"] for r in values): continue
                if mode=="ce" and not all(r["stable"] for r in values): continue
                eligible.extend(r for r in values if r.get(metric) is not None and r[metric]>1e-14)
            fit=bootstrap_rate(eligible,metric,draws=400)
            fits.append(dict(algorithm=alg,mode=mode,method=method,**fit,
                             window="exact rank; r/n<=0.2; N>=128n; CE requires all planned replicates stable",
                             interpretation="CE cost or fixed-policy critic error; NOT a fitted end-to-end NPG/PG/PI complexity"))
    atomic_json(output/"power_fits.json",fits)
    counts={state:sum(r["status"]==state for r in status) for state in ("complete","failed","missing")}
    atomic_json(output/"summary.json",dict(profile=manifest["profile"],counts=counts,tasks=len(status),manifest_sha256=sha))
    plot(output,aggregates,floors,manifest["profile"])
    print(json.dumps(dict(counts=counts,fits=fits)),flush=True)


def plot(output,aggregates,floors,profile):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures=output/"figures";figures.mkdir(exist_ok=True)
    if profile=="scaling":
        fig,axes=plt.subplots(2,3,figsize=(14,8))
        for col,(alg,mode,metric) in enumerate((("CE","ce","gap_mean_available"),("Z","critic","finite_error_fro2_mean_available"),("joint","critic","finite_error_fro2_mean_available"))):
            for method,style in (("raw","--"),("truncated","-")):
                for n,color in ((50,"#116a9b"),(100,"#b0472e")):
                    data=[r for r in aggregates if r["algorithm"]==alg and r["mode"]==mode and r["method"]==method
                          and r["n"]==n and r["N"]==512*n and r.get(metric,0)>0]
                    data.sort(key=lambda r:r["r"])
                    axes[0,col].loglog([r["r"] for r in data],[r[metric] for r in data],style+"o",color=color,label=f"n={n}, {method}")
                data=[r for r in aggregates if r["algorithm"]==alg and r["mode"]==mode and r["method"]==method
                      and r["r"]==4 and r["N"]==512*r["n"] and r.get(metric,0)>0]
                data.sort(key=lambda r:r["n"])
                # N varies with n in this slice: multiply by N to compare rate coefficients.
                axes[1,col].loglog([r["n"] for r in data],[r[metric]*r["N"] for r in data],style+"o",label=method)
            axes[0,col].set_title(f"{alg}: rank sweep, N=512n")
            axes[0,col].set_xlabel("rank r")
            axes[0,col].set_ylabel("Cost gap" if alg=="CE" else "Frobenius error squared")
            axes[1,col].set_title(f"{alg}: dimension sweep, r=4")
            axes[1,col].set_xlabel("dimension n=m")
            axes[1,col].set_ylabel("N x mean error (rate coefficient)")
        for ax in axes.flat:
            ax.grid(alpha=.2);ax.legend(fontsize=7)
        fig.tight_layout();fig.savefig(figures/"dimension_rank.png",dpi=160);plt.close(fig)
    if floors:
        fig,axes=plt.subplots(1,3,figsize=(13,4))
        for ax,alg in zip(axes,("NPG","PG","PI")):
            for n,color in ((50,"#116a9b"),(100,"#b0472e")):
                data=[r for r in floors if r["algorithm"]==alg and r["method"]=="truncated" and r["n"]==n and r["tail_shape"]=="energy" and r["tail"]>0 and r.get("gap") is not None]
                grouped=defaultdict(list)
                for r in data: grouped[r["tail"]].append(r["gap"])
                levels=sorted(grouped)
                ax.loglog([v*v for v in levels],[np.mean(grouped[v]) for v in levels],"o-",color=color,label=f"n={n}")
            ax.set_title(f"{alg}, noiseless finite iteration")
            ax.set_xlabel("B Frobenius tail squared")
            ax.set_ylabel("Absolute cost gap")
            ax.grid(alpha=.2);ax.legend()
        fig.tight_layout();fig.savefig(figures/"approximate_noiseless.png",dpi=160);plt.close(fig)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--manifest",required=True);parser.add_argument("--raw",required=True);parser.add_argument("--output",required=True)
    args=parser.parse_args();run(args.manifest,args.raw,args.output)
