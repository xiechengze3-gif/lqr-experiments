"""X12 calibration and timing on compute nodes; immutable inputs, no retries."""
import argparse, json, os, resource, statistics, time, traceback
from pathlib import Path
import numpy as np
import frozen_engine as e
import estimation
import actor_paths as actor
R=Path(__file__).resolve().parent
OUT=Path('/scratch/user/changze/lqr_experiments/results/x12-20261106')

def verify(config_path):
    e.require_compute();cfg=json.loads(config_path.read_text())
    for name,digest in cfg['sources'].items():assert e.sha(R/name)==digest,name
    assert e.sha(__file__)==cfg['driver_sha256']
    for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']:assert os.environ[key]=='1'
    for key in ['TMPDIR','XDG_CACHE_HOME','NUMBA_CACHE_DIR','MPLCONFIGDIR']:
        assert str(Path(os.environ[key]).resolve()).startswith('/scratch/user/changze/lqr_experiments/')
    assert cfg['actual_cap_SU']==230 and cfg['requested_cap_SU']==300
    return cfg

def calibration(cfg,index):
    assert 0<=index<8
    system=cfg['calibration_systems'][index//4];seed=cfg['calibration_seeds'][index%4]
    dest=OUT/'calibration-v1'/('task-'+str(index));assert not dest.exists();dest.mkdir(parents=True)
    begin=time.monotonic();s=estimation.model('S',60,system)
    np.savez_compressed(dest/'model.npz',**{k:v for k,v in s.items() if k!='certificate'})
    e.save(dest/'certificate.json',s['certificate'])
    target=-s['B'].T@s['P0']@s['A'];sigma2=float(np.linalg.svd(target,compute_uv=False)[1]);assert sigma2>0
    random=e.rng(20,60,60,system,seed,1);rows=[];artifacts=[]
    for item in estimation.stein_prefixes(s,cfg['calibration_grid'],random,dict(H=16,nu=1.,burn_blocks=16)):
        N=item.pop('N');path=dest/('Stein-'+str(N)+'.npz');np.savez_compressed(path,**item)
        rows.append(dict(system=system,seed=seed,N=N,rho_op=float(np.linalg.norm(item['Z']-target,2)/sigma2)))
        artifacts.append(dict(path=path.name,sha256=e.sha(path)))
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;assert peak<.8*2*1024**2
    e.save(dest/'DONE.json',dict(status='COMPLETE',index=index,rows=rows,artifacts=artifacts,
        model_sha256=e.sha(dest/'model.npz'),system=system,seed=seed,seconds=time.monotonic()-begin,
        primitive_transitions=(max(cfg['calibration_grid'])+17)*16,peak_RSS_KiB=peak,
        config_sha256=e.sha(R/'config-protocol-v1.json'),source_sha256=e.sha(__file__),
        estimator_sha256=e.sha(estimation.__file__),engine_sha256=e.sha(e.__file__),job=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='COMPLETE',role='calibration',index=index,seconds=time.monotonic()-begin)),flush=True)

def resolve(cfg):
    dest=OUT/'calibration-resolution-v1';assert not dest.exists();dest.mkdir()
    rows=[];refs=[]
    for index in range(8):
        p=OUT/'calibration-v1'/('task-'+str(index))/'DONE.json';record=json.loads(p.read_text())
        assert record['status']=='COMPLETE' and record['config_sha256']==e.sha(R/'config-protocol-v1.json')
        assert record['estimator_sha256']==e.sha(estimation.__file__) and record['engine_sha256']==e.sha(e.__file__)
        for a in record['artifacts']:assert e.sha(p.parent/a['path'])==a['sha256']
        rows.extend(record['rows']);refs.append(dict(path=str(p),sha256=e.sha(p)))
    summary=[]
    for N in cfg['calibration_grid']:
        medians=[]
        for system in cfg['calibration_systems']:
            values=[x['rho_op'] for x in rows if x['N']==N and x['system']==system];assert len(values)==4
            medians.append(statistics.median(values))
        summary.append(dict(N=N,rho_op_median=statistics.median(medians),system_seed_medians=medians))
    base=next((r['N'] for r in summary if r['rho_op_median']<=1),None)
    schedules=[] if base is None else [dict(n=60,rung=rung,rung_label='r'+str(rung).replace('.',''),
        batches=actor.schedules(base,rung,16,8)) for rung in cfg['rungs']]
    for x in schedules:
        x['primitive_per_arm_per_algorithm']=16*(sum(x['batches']['NPG'])+17*16)
        assert x['primitive_per_arm_per_algorithm']==16*(sum(x['batches']['PI'])+17*8)
    e.save(dest/'DONE.json',dict(status='PASS_CALIBRATION' if base else 'RIGHT_CENSORED_STOP',N_cal=base,
        rule='smallest_registered_N_with_median_of_two_system_four_seed_medians_rho_op_le_1',
        summary=summary,references=refs,all_schedules=schedules,formal_data_used=False,truncated_readout=False,
        new_primitive_transitions=8*(max(cfg['calibration_grid'])+17)*16,job=os.environ['SLURM_JOB_ID'],
        engine_sha256=e.sha(e.__file__),estimator_sha256=e.sha(estimation.__file__),actor_sha256=e.sha(actor.__file__),
        config_sha256=e.sha(R/'config-protocol-v1.json')))
    print(json.dumps(dict(status='PASS_CALIBRATION' if base else 'RIGHT_CENSORED_STOP',N_cal=base,summary=summary)),flush=True)

def timing(cfg,algorithm):
    resolution=OUT/'calibration-resolution-v1/DONE.json';cal=json.loads(resolution.read_text());assert cal['status']=='PASS_CALIBRATION'
    s=estimation.model('S',60,9102);dest=OUT/'timing-v1'/algorithm;assert not dest.exists();dest.mkdir(parents=True)
    begin=time.monotonic();rows=[]
    for x in cal['all_schedules']:
        spec=dict(experiment='X12_RESOURCE_ONLY',n=60,m=60,r=2,system=9102,seed=9801,rung=x['rung'],rung_label=x['rung_label'])
        config=dict(H=16,nu=1.,burn_blocks=16,eta=.2,schedules=x['batches'])
        path=dest/x['rung_label'];result=actor.run(s,spec,config,algorithm,path)
        expected=x['primitive_per_arm_per_algorithm'];assert result['primitive_transitions']==dict(dense=expected,truncated=expected)
        rows.append(dict(rung=x['rung'],algorithm=algorithm,seconds=result['seconds'],primitive_per_arm=expected,done_sha256=e.sha(path/'DONE.json')))
    assert len(rows)==9
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;assert peak<.8*2*1024**2
    e.save(dest/'PILOT_DONE.json',dict(status='PASS',algorithm=algorithm,rows=rows,body_seconds=sum(x['seconds'] for x in rows),
        seconds=time.monotonic()-begin,primitive_transitions=2*sum(x['primitive_per_arm'] for x in rows),
        formal_data_used=False,no_performance_readout=True,peak_RSS_KiB=peak,calibration_sha256=e.sha(resolution),
        engine_sha256=e.sha(e.__file__),actor_sha256=e.sha(actor.__file__),config_sha256=e.sha(R/'config-protocol-v1.json'),job=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='PASS',role='timing',algorithm=algorithm,body_seconds=sum(x['seconds'] for x in rows))),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--role',choices=['calibration','resolve','NPG','PI'],required=True);p.add_argument('--index',type=int);a=p.parse_args()
    cfg=verify(a.config)
    try:
        if a.role=='calibration':calibration(cfg,a.index)
        elif a.role=='resolve':resolve(cfg)
        else:timing(cfg,a.role)
    except BaseException:
        out=OUT/'failures';out.mkdir(exist_ok=True,parents=True)
        e.save(out/(os.environ['SLURM_JOB_ID']+'-'+str(a.index)+'.json'),dict(role=a.role,index=a.index,error=traceback.format_exc(),automatic_retry=False));raise
