"""Initial-certificate and pilot-population calibration for X2/X3 NPG only."""
import json,os
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
import engine as e

GRID=[64,96,128,192,256,384,512,768]
def run(exp,cases,pilot,formal):
    group_results=[]
    for n,spectra in cases:
        rank=2 if exp=='X2' else n;null=.25 if exp=='X2' else 0.
        certs=[e.plant(n,n,rank,s,spectrum=sp,null_scale=null)['certificate'] for s in formal for sp in spectra]
        bound=max(c['P0_op'] for c in certs);eta=1/(1+2*bound);rows=[]
        for system in pilot:
            for spectrum in spectra:
                s=e.plant(n,n,rank,system,spectrum=spectrum,null_scale=null);k=s['K0'].copy();dead=False
                for t in range(1,max(GRID)+1):
                    if not dead:
                        f=s['A']-s['B']@k;p=solve_discrete_lyapunov(f.T,s['Q']+k.T@s['R']@k)
                        k=k-eta*(s['R']@k-s['B'].T@p@f)
                        if not np.all(np.isfinite(k)) or max(abs(np.linalg.eigvals(s['A']-s['B']@k)))>=1-1e-10:dead=True
                    if t in GRID:
                        q=e.assess(s,k) if not dead else dict(stable=False,gap=None,relative_gap=None)
                        rows.append(dict(n=n,system=system,spectrum=spectrum,T=t,**q))
        T=next((t for t in GRID if all(r['stable'] and r['relative_gap']<=.05 for r in rows if r['T']==t)),None)
        group_results.append(dict(n=n,p0_bar=bound,eta=eta,selected_T=T,status='QUALIFIED' if T else 'POPULATION_NOT_QUALIFIED',
          formal_initial_certificates=certs,pilot_population_rows=rows))
    result=dict(experiment=exp,status='COMPLETE_POPULATION_CALIBRATION',groups=group_results,
      formal_learning_outputs_used=False,job=os.environ['SLURM_JOB_ID'],engine_sha256=e.sha(e.__file__),source_sha256=e.sha(__file__))
    e.save(e.OUT/exp/'pilot/NPG_population_calibration.json',result)
    print(json.dumps({'experiment':exp,'groups':[{k:v for k,v in g.items() if not isinstance(v,list)} for g in group_results]}),flush=True)
def main():
    e.require_compute()
    run('X2',[(n,['exact']) for n in [12,24,48]],[9003,9004],range(201,209))
    run('X3',[(12,['smooth','gapped','flat'])],[9005,9006],range(301,309))
if __name__=='__main__':main()
