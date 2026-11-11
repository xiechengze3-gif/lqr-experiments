"""Diagnose saved CSV definitions only, zero new trajectories."""
import csv,json,statistics,sys
from pathlib import Path
import numpy as np
from report_x11 import cost,R,X,sha
old=R.parent/'x6-20261101/CE-addition-v2/deliveries/ce-20365253-v7/X6a/CE-addition-v1/observations.csv'
with old.open(newline='') as f:rows=[r for r in csv.DictReader(f) if r['family']=='S' and r['n']=='48']
Ns=sorted({int(r['N']) for r in rows});out=[]
for arm in ['dense','truncated']:
    raw=[];hier=[]
    for N in Ns:
        group=[r for r in rows if int(r['N'])==N]
        raw.append(statistics.median(float(r[arm+'_gap']) for r in group))
        hier.append(statistics.median(statistics.median(float(r[arm+'_gap']) for r in group if int(r['system'])==s) for s in range(301,309)))
    out.append(dict(arm=arm,Ns=Ns,counts=[sum(int(r['N'])==N for r in rows) for N in Ns],raw_median=raw,system_median=hier,
        raw_cross=cost(np.array(Ns,float),np.array(raw),.01),system_cross=cost(np.array(Ns,float),np.array(hier),.01),
        raw_transition_cross=cost(np.array(Ns,float)+512,np.array(raw),.01),system_transition_cross=cost(np.array(Ns,float)+512,np.array(hier),.01)))
paper=Path('C:/Users/24375/Projects/project2_l4dc/figs/data/X6a_CE_full_gaps.csv')
with paper.open(newline='') as f:paperrows=[r for r in csv.DictReader(f) if r['family']=='S' and r['n']=='48']
for arm,key in [('dense','dense_abs_gap'),('truncated','trunc_abs_gap')]:
    out.append(dict(arm=arm,paper_rounded_cross=cost(np.array([float(r['N']) for r in paperrows]),np.array([float(r[key]) for r in paperrows]),.01)))
print(json.dumps(out,indent=2))
