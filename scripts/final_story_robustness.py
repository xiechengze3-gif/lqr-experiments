"""Cost-only evaluation on perturbed plants; nominal Jstar is not a lower bound."""
import json
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from final_story import OUT,CFG,plant,assess,op,rng_for,identity,provenance,atomic_json


def robustness():
    rows=[]
    for p in sorted((OUT/'formal').glob('*.json')):
        d=json.loads(p.read_text());t=d['spec']
        if t['family']!='E1' or t.get('m')!=12 or t['algorithm']=='CE':continue
        s,basis,_=plant('E1',t['system'],12)
        k=np.load(p.with_suffix('.npz'))['policies'][-1]
        nominal=assess(s,k);denom=nominal.get('cost')
        stage_cost=s['Q']+k.T@s['R']@k
        for direction in range(10):
            perturb=rng_for(246400,t['system'],direction).normal(size=(12,12))
            perturb-=perturb@basis@basis.T;perturb/=op(perturb)
            assert np.linalg.norm(perturb@basis)<1e-11
            for delta in [0.,1.,2.,4.,8.,16.]:
                f=s['A']-(s['B']+delta*perturb)@k
                rho=float(np.max(np.abs(np.linalg.eigvals(f))))
                stable=d['status']=='complete' and rho<1-1e-10
                cost=float(np.trace(solve_discrete_lyapunov(f.T,stage_cost))) if stable else None
                change=(cost-denom)/denom if stable and nominal['stable'] else None
                if delta==0 and stable:assert abs(change)<1e-11
                rows.append(dict(id=t['id'],system=t['system'],trial=t['trial'],algorithm=t['algorithm'],
                    mode=t['mode'],direction=direction,delta=delta,nominal_complete=d['status']=='complete',
                    stable=stable,relative_change=change,
                    absolute_relative_change=abs(change) if change is not None else None,
                    perturbed_cost=cost,perturbed_rho=rho))
    atomic_json(OUT/'robustness.json',dict(rows=rows,identity=identity(),provenance=provenance(),
        additional_training_transitions=0,deployment_transitions=0,
        evaluation='Direct stationary cost on each perturbed plant; signed improvements allowed.'))
