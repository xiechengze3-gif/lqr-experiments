"""R1/R2 actor calibration required by Claude's 01:20 review; pilot truth only."""
import json,os
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
import engine as e

def main():
    e.require_compute();cfg=json.loads((Path(__file__).parent/'configs/X1_v1.json').read_text())
    certs=[];largest=0.
    for system in cfg['formal_systems']:
        for null in (0.,.25):
            for m in cfg['ms']:
                if null and m==2:continue
                s=e.plant(12,m,2,system,null_scale=null);cert=s['certificate'];certs.append(cert);largest=max(largest,cert['P0_op'])
    eta=1/(1+2*largest);np_rows=[];pi_rows=[]
    for system in cfg['pilot_systems']:
        for null in (0.,.25):
            for m in cfg['ms']:
                if null and m==2:continue
                s=e.plant(12,m,2,system,null_scale=null);k=s['K0'].copy()
                for t in range(1,193):
                    f=s['A']-s['B']@k;p=solve_discrete_lyapunov(f.T,s['Q']+k.T@s['R']@k)
                    z=-s['B'].T@p@f;k=k-eta*(s['R']@k+z)
                    if t in (64,96,128,192):np_rows.append(dict(system=system,m=m,null_scale=null,T=t,**e.assess(s,k)))
                k=s['K0'].copy()
                for t in range(1,13):
                    f=s['A']-s['B']@k;p=solve_discrete_lyapunov(f.T,s['Q']+k.T@s['R']@k)
                    g=s['B'].T@p@s['B'];z=-s['B'].T@p@f
                    k=e.actor_learner(k,s['R'],g,z,'dense',m,'PI',1.)
                    if t in (8,12):pi_rows.append(dict(system=system,m=m,null_scale=null,T=t,**e.assess(s,k)))
    def choose(data,grid):
        return next((t for t in grid if all(r['stable'] and r['relative_gap']<=.05 for r in data if r['T']==t)),None)
    npg_T=choose(np_rows,(64,96,128,192));pi_T=choose(pi_rows,(8,12))
    result=dict(status='PASS' if npg_T and pi_T else 'POPULATION_TARGET_NOT_REACHED',
      rule='Claude R1/R2, review01:20',p0_bar=largest,B_operator_norm=1.,mu_plus=1.,eta=eta,
      selected_npg_T=npg_T,selected_pi_T=pi_T,formal_initial_certificates=certs,
      pilot_population_NPG=np_rows,pilot_population_PI=pi_rows,
      no_formal_learning_outputs_used=True,job=os.environ['SLURM_JOB_ID'],engine_sha256=e.sha(e.__file__),calibration_sha256=e.sha(__file__))
    e.save(e.OUT/'X1/pilot/revised-r1-r2.json',result)
    print(json.dumps({k:v for k,v in result.items() if not isinstance(v,list)}))

if __name__=='__main__':main()
