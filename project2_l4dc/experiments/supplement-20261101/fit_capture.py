"""Store the exact same observed OLS fits for pilot calibration; no new sampling."""
import json
from pathlib import Path
import numpy as np
import engine as e
from formal_driver import execute

def captured_ce(s,spec,cfg,path):
    original=e.fit_model;count=0;fits={}
    def fit(gram,cross):
        nonlocal count
        theta=original(gram,cross);index,half=divmod(count,3);N=cfg['ce_prefixes'][index]
        fits[f'theta_{N}_{("full","first","second")[half]}']=theta.copy();count+=1
        return theta
    e.fit_model=fit
    try:data=execute(s,spec,cfg,'CE',path)
    finally:e.fit_model=original
    assert count==3*len(cfg['ce_prefixes'])
    np.savez_compressed(path.with_name(path.stem+'.fits.npz'),**fits)
    return data

def main():
    e.require_compute();root=Path(__file__).parent;cfg=json.loads((root/'configs/X3_v1.json').read_text())
    out=e.OUT/'X3/pilot/CE';out.mkdir(parents=True,exist_ok=True)
    rows=[];C5_max=0.
    for system in cfg['pilot_systems']:
        for trial in cfg['pilot_trials']:
            for case in cfg['ce_cases']:
                n=case['n'];spectrum=case['spectrum'];s=e.plant(n,n,n,system,spectrum=spectrum)
                spec=dict(experiment='X3',n=n,m=n,r=n,system=system,trial=trial,spectrum=spectrum,null_scale=0.)
                resolved=dict(cfg,ce_prefixes=case['prefixes'],fixed_ranks=case['fixed_ranks'])
                path=out/f'n{n}-{spectrum}-s{system}-t{trial}.json';assert not path.exists()
                captured_ce(s,spec,resolved,path)
                with np.load(path.with_name(path.stem+'.fits.npz')) as fits:
                    for N in case['prefixes']:
                        bh=fits[f'theta_{N}_full'][:,n:];scale=np.sqrt((2*n+np.log(1/cfg['delta']))/N)
                        val=float(np.linalg.norm(bh-s['B'],2)/scale);C5_max=max(C5_max,val)
                        rows.append(dict(n=n,spectrum=spectrum,system=system,trial=trial,N=N,dense_B_error_normalized=val))
    result=dict(status='COMPLETE',C5=1.25*C5_max,delta=cfg['delta'],rule='1.25 x maximum normalized dense Bhat operator error on pilot fits only',
      adaptive_performance_not_used=True,no_formal_learning_outputs_used=True,rows=rows,engine_sha256=e.sha(e.__file__),capture_sha256=e.sha(__file__))
    e.save(e.OUT/'X3/pilot/C5_calibration.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))

if __name__=='__main__':main()
