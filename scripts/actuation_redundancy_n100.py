"""n100 entrypoint; preserve the frozen n30 scientific engine unchanged."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.linalg import cho_factor, cho_solve
import actuation_redundancy as engine

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'configs/actuation_redundancy_n100_20261016.json'
engine.SOURCES=list(engine.SOURCES)+[
    'scripts/actuation_redundancy_n100.py',
    'scripts/actuation_redundancy_figures.py',
    'scripts/Invoke-ActuationRedundancyN100.ps1',
    'docs/ACTUATION_REDUNDANCY_N100_PROTOCOL_20261016.md']

# Sharing violations are infrastructure failures. Retry only the same complete
# temporary-file replacement; do not repeat sampling or change optimizer state.
_replace=os.replace
def replace_retry(source,destination):
    for attempt in range(41):
        try:return _replace(source,destination)
        except PermissionError:
            if attempt==40:raise
            time.sleep(.05)
os.replace=replace_retry

_verify=engine.verify
def verify(cfg,out,ident):
    assert cfg['n']==100 and cfg['rank']==4
    _verify(cfg,out,ident)
    geometry=[]
    from dense_scaling import targets
    from direct_stein_final import sufficient,fit
    rng=engine.rng_for(930011)
    starts=rng.normal(size=(400,100));pulses=rng.normal(size=(400,128));returns=rng.normal(size=400)
    stats=sufficient(starts,pulses,returns,17.,cfg['sigma'])
    labels=-pulses*np.diff(np.r_[17.,returns])[:,None]/(2*cfg['sigma']**2)
    expected=cho_solve(cho_factor(starts.T@starts),(labels.T@starts).T).T
    np.testing.assert_allclose(expected,fit(stats)[1],atol=1e-12)
    for m in cfg['action_dimensions']:
        s,private=engine.make_system(cfg,m)
        z=targets(s,s['K0'],cfg['horizon'])['ZH']
        dense=engine.learner(s['K0'],z,'dense',cfg['eta'],cfg['rank'])
        truncated=engine.learner(s['K0'],z,'truncated',cfg['eta'],cfg['rank'])
        np.testing.assert_allclose(dense,truncated,atol=1e-12)
        assert np.linalg.matrix_rank(z,tol=1e-8)<=4
        assert np.linalg.matrix_rank(truncated,tol=1e-8)>4
        geometry.append(dict(m=m,n=100,ambient_gain_rank_cap=min(m,100),
                             initial_gain_rank=int(np.linalg.matrix_rank(s['K0'],tol=1e-8)),
                             population_Z_rank=int(np.linalg.matrix_rank(z,tol=1e-8)),
                             population_updated_gain_rank=int(np.linalg.matrix_rank(truncated,tol=1e-8))))
    path=Path(out)/'verification.json';data=json.loads(path.read_text())
    data['rank_geometry']=geometry
    data['tests']+=['n100 m128 original first-order fit equivalence',
                    'gain rank cap distinct from action-space alignment',
                    'truncating Z does not force rank4 K',
                    'population dense/truncated updates coincide at every m']
    engine.atomic_json(path,data)
    print(json.dumps(dict(n100_extra_checks='PASS',rank_geometry=geometry)),flush=True)
engine.verify=verify


def main():
    if len(sys.argv)>1 and sys.argv[1]=='report':
        parser=argparse.ArgumentParser();parser.add_argument('mode');parser.add_argument('--manifest',type=Path,default=MANIFEST)
        args=parser.parse_args();cfg=json.loads(args.manifest.read_text())
        import actuation_redundancy_report as report
        import actuation_redundancy_figures as figures
        report.report(cfg['output']);figures.main(cfg['output'])
        path=Path(cfg['output'])/'report/findings.md'
        path.write_text(path.read_text(encoding='utf-8').replace('n30/r4','n100/r4'),encoding='utf-8')
    else:
        if '--manifest' not in sys.argv:sys.argv+=['--manifest',str(MANIFEST)]
        engine.main()


if __name__=='__main__':main()
