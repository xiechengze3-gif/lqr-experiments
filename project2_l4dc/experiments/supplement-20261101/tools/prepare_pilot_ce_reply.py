"""Saved-result pilot accounting and append-ready CE replies; no simulations."""
import csv,json,math
from collections import Counter,defaultdict
from pathlib import Path
from control import ROOT,sha,write

def quant(values,p):
    a=sorted(values);at=p*(len(a)-1);l,h=math.floor(at),math.ceil(at)
    if l==h or a[l]==a[h]:return a[l]
    return math.inf if math.isinf(a[h]) else a[l]+(at-l)*(a[h]-a[l])

for exp in ['X2','X3']:
    paths=sorted(p for p in (ROOT/exp/'pilot/CE').glob('*.json') if not p.name.endswith('.audit.json'))
    raw=[];timings=[]
    for path in paths:
        data=json.loads(path.read_text());raw.extend(data['records']);timings.append(data['seconds'])
    cfg=ROOT/'configs'/('X2_v1.json' if exp=='X2' else 'X3_CE_resolved_v2.json')
    adaptive=ROOT/'X3/pilot-adaptive/SUMMARY.json'
    if exp=='X3':
        assert adaptive.is_file(), 'Both adaptive pilots must complete before PILOT DONE'
        for path in sorted((ROOT/'X3/pilot-adaptive').glob('n*.json')):
            data=json.loads(path.read_text());raw.extend(data['records']);timings.append(data['seconds'])
    groups=defaultdict(list)
    for row in raw:groups[(row['n'],row['r'],row['spectrum'],row['N'],row['mode'])].append(row)
    table=[]
    for key,rows in sorted(groups.items()):
        assert len(rows)==4 and len({(r['system'],r['trial']) for r in rows})==4
        for metric in ['gap','relative_gap']:
            values=[r[metric] if r['stable'] else math.inf for r in rows]
            table.append(dict(n=key[0],r=key[1],spectrum=key[2],N=key[3],mode=key[4],metric=metric,
              count=4,stable_count=sum(r['stable'] for r in rows),median=quant(values,.5),q25=quant(values,.25),q75=quant(values,.75)))
    dest=ROOT/exp/'pilot-ce-statistics.csv'
    with dest.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    counts=Counter(r['mode'] for r in raw if not r['stable'])
    body=f'Scope: **{exp} CE-only pilot**; NPG is a separate calibrated branch.\n\n'
    body+=f'Complete shared-data coverage: {len(paths)} continuous trajectories; {len(raw)} evaluated outputs, '
    body+=f'{sum(not r["stable"] for r in raw)} failed/unstable outputs retained. '
    body+='Failure-inclusive medians/IQR and all four-repeat stable counts are in '
    body+=f'`{exp}/pilot-ce-statistics.csv`; raw policies/fit archives and delivery hashes are local.\n\n'
    body+='| Method | Failed / all tested outputs |\n|---|---:|\n'
    for mode in sorted({r['mode'] for r in raw}):
        body+=f'| {mode} | {counts[mode]}/{sum(r["mode"]==mode for r in raw)} |\n'
    body+='\nAt the largest regression prefix per case (medians [IQR]):\n\n'
    body+='| n | rank / spectrum | Method | Absolute gap | Relative gap | Stable |\n|---:|---|---|---|---|---:|\n'
    keys=sorted({(r['n'],r['r'],r['spectrum'],r['mode']) for r in raw if r['mode'] in ['dense','truncated','adaptive_paper','adaptive_split']})
    for n,r,sp,mode in keys:
        rows=[x for x in table if x['n']==n and x['r']==r and x['spectrum']==sp and x['mode']==mode]
        N=max(x['N'] for x in rows);g=next(x for x in rows if x['N']==N and x['metric']=='gap');rel=next(x for x in rows if x['N']==N and x['metric']=='relative_gap')
        fmt=lambda z:f"{z['median']:.5g} [{z['q25']:.5g}, {z['q75']:.5g}]"
        body+=f"| {n} | {r if exp=='X2' else sp} | {mode} | {fmt(g)} | {fmt(rel)} | {g['stable_count']}/4 |\n"
    if exp=='X2':
        body+='\nMeasured pilot: worst complete Slurm bundle37s, largest per-trajectory6.761331s, '
        body+='peak sampled MaxRSS148588KiB; single-core billing1. Formal request:32 bundles '
        body+='x2min x1core/2GiB=1.066667SU upper. The2min request exceeds1.3*37+30=78.1s. '
        body+='No CE hyperparameter is changed based on these outcomes.\n'
    else:
        body+='\nGlobal C5=2.569143010355372 from432 dense-fit error diagnostics only; '
        body+='delta.05. Both adaptive variants reuse the24 captured trajectories and exact full/half OLS fits; '
        body+='adaptive postprocessing samples zero new transitions. Conservative paper-form threshold failures '
        body+='are retained; the constant is not tuned to adaptive policy performance.\n'
        body+='\nThe fixed-order pilot job completed36s for all24 trajectories, peak sampled RSS145192KiB. '
        body+='The formal32 bundles x2min x1core/2GiB bound1.066667SU leaves allowance for both adaptive solvers. '
        body+='Full-rank flat-spectrum results and k0 failures remain visible.\n'
    body+=f'\nResolved config `{cfg.relative_to(ROOT)}`, SHA256 `{sha(cfg)}`; engine '
    body+=f'`{sha(ROOT/"engine.py")}`. **Formal remains blocked pending explicit {exp} CE ACCEPTED**, '
    body+='not a60-minute timeout. NPG calibration does not reuse these CE outcomes.\n'
    (ROOT/exp/'ce_pilot_reply.md').write_bytes(body.encode())
    write(ROOT/exp/'CE_PILOT_VERIFIED.json',dict(status='PASS',scope='CE_ONLY',trajectories=len(paths),outputs=len(raw),
       unstable_outputs=sum(not r['stable'] for r in raw),failures_by_mode=dict(counts),config_sha256=sha(cfg)))
    print(json.dumps(dict(experiment=exp,trajectories=len(paths),outputs=len(raw),failures_by_mode=dict(counts),reply_ready=True)))
