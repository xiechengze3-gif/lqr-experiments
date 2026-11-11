"""X7 resource-only pilot and frozen formal bundles; all numerics on Slurm."""
from __future__ import annotations
import argparse
import json
import os
import resource
import time
from pathlib import Path
import frozen_engine as e
import ce_fullrank as c


def cases(config):
    return [(n,spectrum) for n in config['n_values'] for spectrum in config['spectra']]


def resource_pilot(config_path,index):
    c.require_compute();config_path=Path(config_path)
    config=json.loads(config_path.read_text());c.verify_sources(config)
    assert config['status']=='PROTOCOL_FROZEN' and 0<=index<4
    n,spectrum=cases(config)[index];case=f'n{n}-{spectrum}'
    directory=c.OUT/'resource-v1'/case
    assert not directory.exists();directory.mkdir(parents=True)
    started=time.monotonic();model_start=time.monotonic()
    formal_registry={};pilot_registry={};pilot_models={}
    # Deterministic formal inputs only:no formal observations,fit or gap selection.
    for system in config['formal_systems']+config['pilot_systems']:
        model=c.make_model(n,spectrum,system)
        reference=c.save_model(model,c.OUT/'resource-v1/models'/case/f's{system}')
        key=f'{case}-s{system}'
        if system in config['formal_systems']:formal_registry[key]=reference
        else:
            pilot_registry[key]=reference
            pilot_models[system]=model
    model_seconds=time.monotonic()-model_start
    rows=[];first=None
    for system in config['pilot_systems']:
        model=pilot_models[system]
        reference=pilot_registry[f'{case}-s{system}']
        for trial in config['pilot_seeds']:
            spec=dict(experiment='X7',n=n,m=n,r=n,system=system,trial=trial,spectrum=spectrum)
            path=directory/'paths'/f's{system}-t{trial}'
            result=c.run_path(model,spec,config,path,e.sha(config_path),reference['sha256'])
            rows.append(dict(n=n,spectrum=spectrum,system=system,trial=trial,
                seconds=result['seconds'],peak_RSS_KiB=result['peak_RSS_KiB'],
                primitive_transitions=result['primitive_transitions'],
                newly_collected_transitions=result['newly_collected_transitions'],
                path=str(path),done_sha256=e.sha(path/'DONE.json')))
            if first is None:first=(model,spec,dict(result,_directory=str(path)))
    model,spec,result=first
    reference_path=directory/'reference/ce_run.json'
    equivalence=c.reference_equivalence(model,spec,config,result,reference_path)
    # Resource readout deliberately excludes every gap,stability and selected order.
    timing=dict(status='COMPLETE_RESOURCE_ONLY',n=n,spectrum=spectrum,
        config_sha256=e.sha(config_path),source_sha256=e.sha(__file__),
        core_sha256=e.sha(c.__file__),engine_sha256=e.sha(e.__file__),
        model_preparation_seconds=model_seconds,formal_model_count=len(formal_registry),
        formal_model_training_transitions=0,rows=rows,equivalence=equivalence,
        formal_model_registry=formal_registry,pilot_model_registry=pilot_registry,
        reference_done_sha256=e.sha(reference_path),
        primitive_transitions=sum(r['primitive_transitions'] for r in rows)+max(c.prefixes(config,n))+512,
        automatic_retries=0,seconds=time.monotonic()-started,
        peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        no_performance_readout=True,job=os.environ['SLURM_JOB_ID'])
    c.save_new(directory/'timing.json',timing)
    print(json.dumps({k:v for k,v in timing.items()
        if k not in ['formal_model_registry','pilot_model_registry','rows']}))


def formal(config_path,index):
    c.require_compute();config_path=Path(config_path)
    config=json.loads(config_path.read_text());c.verify_sources(config)
    assert config['status']=='FORMAL_FROZEN' and 0<=index<32
    system=config['formal_systems'][index//4];trial=config['formal_seeds'][index%4]
    directory=c.OUT/'formal-v1'/f'task-{index}'
    assert not directory.exists();directory.mkdir(parents=True)
    started=time.monotonic();paths=[]
    for n,spectrum in cases(config):
        case=f'n{n}-{spectrum}'
        reference=config['model_registry'][f'{case}-s{system}']
        model=c.load_model(reference['path'],reference['sha256'])
        spec=dict(experiment='X7',n=n,m=n,r=n,system=system,trial=trial,spectrum=spectrum)
        path=directory/case
        result=c.run_path(model,spec,config,path,e.sha(config_path),reference['sha256'])
        paths.append(dict(case=case,path=case,done_sha256=e.sha(path/'DONE.json'),
            primitive_transitions=result['primitive_transitions'],
            rows=len(result['records']),seconds=result['seconds']))
        print(json.dumps(dict(case=case,status='COMPLETE',rows=len(result['records']))),flush=True)
    assert len(paths)==4 and sum(r['rows'] for r in paths)==336
    assert sum(r['primitive_transitions'] for r in paths)==1181696
    receipt=dict(status='COMPLETE',index=index,system=system,trial=trial,paths=paths,
        config_sha256=e.sha(config_path),source_sha256=e.sha(__file__),
        core_sha256=e.sha(c.__file__),engine_sha256=e.sha(e.__file__),
        primitive_transitions=sum(r['primitive_transitions'] for r in paths),
        seconds=time.monotonic()-started,job=os.environ['SLURM_JOB_ID'],
        peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    c.save_new(directory/'BUNDLE_DONE.json',receipt)
    print(json.dumps(receipt))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['resource','formal'])
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--index',type=int,required=True)
    args=parser.parse_args()
    if args.stage=='resource':resource_pilot(args.config,args.index)
    else:formal(args.config,args.index)
