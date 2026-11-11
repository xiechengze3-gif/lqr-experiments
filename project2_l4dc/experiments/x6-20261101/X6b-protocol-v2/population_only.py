"""Proposed zero-sample R2 design job; wait for X6b protocol ACCEPTED."""
import argparse
import json
import os
import time
from pathlib import Path
import frozen_engine as e
import population_core as core


def main():
    e.require_compute()
    p=argparse.ArgumentParser();p.add_argument('--config',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    allowed=Path('/scratch/user/changze/lqr_experiments/results/x6-20261101/X6b')
    assert a.out.resolve().is_relative_to(allowed) and not a.out.exists()
    config=json.loads(a.config.read_text(encoding='utf-8-sig'))
    assert config['eta']==.2 and config['n_values']==[24,36,48,72]
    assert config['npg_bases']=={'24':524288,'36':1048576,'48':2097152,'72':4194304}
    start=time.monotonic();result=core.population(config)
    ready=all(result['selected_T'].values())
    a.out.mkdir(parents=True)
    data=dict(status='POPULATION_READY' if ready else 'POPULATION_TARGET_NOT_REACHED',
        population=result,job=os.environ['SLURM_JOB_ID'],seconds=time.monotonic()-start,
        new_primitive_transitions=0,source_sha256=e.sha(__file__),core_sha256=e.sha(core.__file__),
        engine_sha256=e.sha(e.__file__),config_sha256=e.sha(a.config))
    e.save(a.out/'population.json',data)
    print(json.dumps({k:v for k,v in data.items() if k!='population'}))


if __name__=='__main__':main()
