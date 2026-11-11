"""Paired seed bootstrap on saved CE diagnostics; no new systems or trajectories."""
import csv
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
source=Path('E:/ChatGPT/Results/LQR_experiments/matched-gap-npg-pi-20261019/ce-identification-audit/all_diagnostics.csv')
rows=list(csv.DictReader(source.open(encoding='utf-8-sig')))
rows=[r for r in rows if r['source']=='saved_final_joint_OLS']
indices=np.random.default_rng(2026101904).integers(0,30,size=(2000,30))


def vector(rank,variant,field='gap'):
    rr=sorted([r for r in rows if int(r['rank'])==rank and r['variant']==variant],key=lambda r:int(r['seed']))
    assert len(rr)==30 and [int(r['seed']) for r in rr]==list(range(200,230))
    return np.array([float(r[field]) for r in rr])


def ratio(name,a,b):
    boot=np.median(a[indices],axis=1)/np.median(b[indices],axis=1)
    return dict(comparison=name,point=float(np.median(a)/np.median(b)),
        paired_bootstrap95=np.quantile(boot,[.025,.975]).tolist())


stats=[ratio('rank2 dense gap / rank2 truncated gap',vector(2,'dense'),vector(2,'truncated')),
    ratio('rank2 truncated gap / same Bhat with true A',vector(2,'truncated'),vector(2,'known_A_truncated_B')),
    ratio('rank2 known-A dense gap / rank2 known-A truncated gap',vector(2,'known_A_dense_B'),vector(2,'known_A_truncated_B')),
    ratio('full-rank dense gap / rank2 truncated gap',vector(100,'dense'),vector(2,'truncated')),
    ratio('known-A full-rank dense gap / known-A rank2 truncated gap',vector(100,'known_A_dense_B'),vector(2,'known_A_truncated_B')),
    ratio('rank2 A model error / full-rank A model error',vector(2,'dense','A_error_fro2'),vector(100,'dense','A_error_fro2')),
    ratio('full-rank dense B model error / rank2 truncated B model error',vector(100,'dense','B_error_fro2'),vector(2,'dense','B_truncated_error_fro2'))]
out=ROOT/'analysis/ce-identification-audit-20261019';out.mkdir(parents=True,exist_ok=True)
result=dict(source=str(source),seeds=list(range(200,230)),transitions=131328,bootstrap_seed=2026101904,
    bootstrap_replicates=2000,scope='Paired ratio of medians; conditional on the frozen system family. Oracle parameter substitutions occur only at the Riccati input, without refitting the other parameter.',comparisons=stats)
(out/'paired_diagnostic_statistics.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(stats))
