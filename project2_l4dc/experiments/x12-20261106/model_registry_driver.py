"""One-time compute-node construction of fixed formal models; zero observations."""
import argparse,json,os,time
from pathlib import Path
import numpy as np
import frozen_engine as e
import estimation

def main(protocol,gate_path,out):
    e.require_compute();cfg=json.loads(protocol.read_text());gate=json.loads(gate_path.read_text())
    assert gate['status']=='ALL_PILOT_COST_GATES_PASS'
    assert gate['actual_forecast_SU']<=230 and gate['requested_upper_SU']<=300
    root=Path('/scratch/user/changze/lqr_experiments/results/x12-20261106')
    assert out.resolve().is_relative_to(root) and not out.exists()
    assert cfg['n']==cfg['m']==60 and cfg['rank']==2
    assert cfg['formal_systems']==list(range(301,309))
    assert e.sha(e.__file__)==cfg['sources']['frozen_engine.py'] and e.sha(estimation.__file__)==cfg['sources']['estimation.py']
    out.mkdir(parents=True);start=time.monotonic();models={}
    for system in cfg['formal_systems']:
        s=estimation.model('S',60,system);name='n60-s'+str(system)+'.npz';path=out/name
        np.savez_compressed(path,**{k:v for k,v in s.items() if k!='certificate'})
        models['n60-s'+str(system)]=dict(path=name,sha256=e.sha(path),certificate=s['certificate'])
    receipt=dict(status='FORMAL_MODELS_FIXED_NO_OBSERVATIONS',models=models,
        simulated_transitions=0,source_sha256=e.sha(__file__),engine_sha256=e.sha(e.__file__),estimator_sha256=e.sha(estimation.__file__),
        protocol_sha256=e.sha(protocol),gate_sha256=e.sha(gate_path),job=os.environ['SLURM_JOB_ID'],seconds=time.monotonic()-start,
        no_plant_selection=True,formal_sampling_not_started=True)
    with (out/'DONE.json').open('x') as f:json.dump(receipt,f,indent=2)
    print(json.dumps({k:v for k,v in receipt.items() if k!='models'}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--protocol',type=Path,required=True);p.add_argument('--gate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.protocol,a.gate,a.out)
