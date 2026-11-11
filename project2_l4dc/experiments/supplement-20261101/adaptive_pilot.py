"""X3 adaptive pilot from captured OLS fits only: zero sampled transitions."""
import json,math,os,time
from pathlib import Path
import numpy as np
from scipy.linalg import solve_discrete_are,solve_discrete_lyapunov
import engine as e

C5=2.569143010355372
DELTA=.05

def main():
    e.require_compute();source=e.OUT/'X3/pilot/CE';dest=e.OUT/'X3/pilot-adaptive'
    assert not dest.exists();dest.mkdir()
    calibration=e.OUT/'X3/pilot/C5_calibration.json';cal=json.loads(calibration.read_text())
    assert cal['status']=='COMPLETE' and cal['C5']==C5
    files=sorted(p for p in source.glob('*.json') if not p.name.endswith('.audit.json'))
    assert len(files)==24
    items=[];all_rows=[]
    for path in files:
        begun=time.monotonic();data=json.loads(path.read_text());spec=data['spec'];n,m=spec['n'],spec['m']
        with np.load(path.with_suffix('.npz')) as z:a,b,k0=z['A'],z['B'],z['K0']
        ps=solve_discrete_are(a,b,np.eye(n),np.eye(m));ks=np.linalg.solve(np.eye(m)+b.T@ps@b,b.T@ps@a)
        s=dict(A=a,B=b,K0=k0,Q=np.eye(n),R=np.eye(m),W=np.eye(n),Pstar=ps,Kstar=ks,basis=None,certificate=data['certificate'])
        p0=solve_discrete_lyapunov((a-b@k0).T,np.eye(n)+k0.T@k0)
        assert abs(float(np.trace(p0-ps))-data['certificate']['initial_gap'])<1e-8
        rows=[];policies={};fits_path=path.with_name(path.stem+'.fits.npz')
        with np.load(fits_path) as fits:
            for N in sorted(set(r['N'] for r in data['records'])):
                theta=fits[f'theta_{N}_full'];bh=theta[:,n:];singular=np.linalg.svd(bh,compute_uv=False)
                proxy=float(np.linalg.norm(fits[f'theta_{N}_first'][:,n:]-fits[f'theta_{N}_second'][:,n:],2)/2)
                thresholds=[('adaptive_paper',C5*math.sqrt((n+m+math.log(1/DELTA))/N)),('adaptive_split',proxy)]
                for mode,threshold in thresholds:
                    k=int(np.count_nonzero(singular>threshold));row=dict(spec,algorithm='CE',mode=mode,k=k,N=N,transitions=N+512,threshold=threshold)
                    try:
                        gain=e.ce_learner(theta,n,s['Q'],s['R'],k)
                        policies[f'{N}_{mode}']=gain;row.update(e.assess(s,gain))
                    except (np.linalg.LinAlgError,ValueError,ArithmeticError) as exc:
                        row.update(stable=False,gap=None,relative_gap=None,failure=repr(exc))
                    rows.append(row)
        out=dest/path.name
        np.savez_compressed(out.with_suffix('.npz'),A=a,B=b,K0=k0,**policies)
        result=dict(spec=spec,certificate=data['certificate'],records=rows,seconds=time.monotonic()-begun,
          source_json_sha256=e.sha(path),source_fits_sha256=e.sha(fits_path),calibration_sha256=e.sha(calibration),
          C5=C5,delta=DELTA,new_training_transitions=0,source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),job=os.environ['SLURM_JOB_ID'])
        e.save(out,result);items.append(dict(path=str(out),sha256=e.sha(out),seconds=result['seconds']));all_rows.extend(rows)
    assert len(all_rows)==864
    summary=dict(status='COMPLETE',outputs=864,trajectories_reused=24,new_training_transitions=0,
       C5=C5,delta=DELTA,selection_did_not_use_adaptive_performance=True,items=items,
       failures={mode:sum(not r['stable'] for r in all_rows if r['mode']==mode) for mode in ['adaptive_paper','adaptive_split']},
       source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),job=os.environ['SLURM_JOB_ID'])
    e.save(dest/'SUMMARY.json',summary);print(json.dumps({k:v for k,v in summary.items() if k!='items'}))

if __name__=='__main__':main()
