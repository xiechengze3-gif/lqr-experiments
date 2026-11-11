"""The23:00-authorized S/n36 dense-only extension; no population/actor run."""
import argparse
import json
import os
import time
from pathlib import Path
import frozen_engine as e
import estimation
import extension_core as core


def main():
    e.require_compute()
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    allowed=Path('/scratch/user/changze/lqr_experiments/results/x6-20261101/X6a')
    assert a.out.resolve().is_relative_to(allowed) and not a.out.exists()
    config=json.loads(a.config.read_text(encoding='utf-8-sig'))
    assert config['n36_extension_grid']==[1048576,2097152]
    a.out.mkdir(parents=True);start=time.monotonic()
    equality=core.resume_equivalence()
    extension=core.extend_n36(config,a.out)
    data=dict(status='QUALIFIED' if extension['selected_base'] else 'RIGHT_CENSORED',
        family='S',n=36,experiment='X6a_A2',extension=extension,
        resume_equivalence=equality,population_R2_run=False,truncated_readout=False,
        new_primitive_transitions=extension['additional_transitions']+66080,
        seconds=time.monotonic()-start,job=os.environ['SLURM_JOB_ID'],
        source_sha256=e.sha(__file__),core_sha256=e.sha(core.__file__),
        engine_sha256=e.sha(e.__file__),estimator_sha256=e.sha(estimation.__file__),
        config_sha256=e.sha(a.config))
    e.save(a.out/'extension.json',data)
    print(json.dumps({k:v for k,v in data.items() if k!='extension'}))


if __name__=='__main__':main()
