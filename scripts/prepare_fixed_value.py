"""Declare controlled contrasts and fixed batches before sampled learning."""
import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    base=dict(n=50,m=50,r=4,family='orthogonal',spectrum='exact',policy_seed=1,initial_strength=.08)
    changes=[('orth-exact',{}),('orth-tail003',dict(spectrum='tail003')),
        ('orth-tail010',dict(spectrum='tail010')),('orth-decay',dict(spectrum='decay')),
        ('orth-flat',dict(spectrum='flat')),('nonnormal-exact',dict(family='nonnormal')),
        ('unstable-exact',dict(family='unstable')),('anisotropic-exact',dict(family='anisotropic')),
        ('orth-rank2',dict(r=2)),('orth-rank8',dict(r=8)),
        ('orth-initweak',dict(policy_seed=0,initial_strength=.04)),
        ('orth-initstrong',dict(policy_seed=2,initial_strength=.12))]
    tasks=[]
    for index,(name,change) in enumerate(changes):
        for profile in (('standard','low','high') if name=='orth-exact' else ('standard',)):
            for seed in (10,11,12):
                for trial in (0,1):
                    tasks.append(dict(base,**change,id=len(tasks),scenario=name,scenario_index=index,
                                      profile=profile,system_seed=seed,trial_seed=trial))
    profiles={}
    for name,ce,direct,npg in [('low',32768,262144,131072),
                             ('standard',65536,524288,262144),('high',262144,1048576,524288)]:
        profiles[name]={alg:dict(batch=batch,stages=stages) for alg,batch,stages in
                       [('CE',ce,8),('LSTD_PI',ce,8),('DIRECT_PI',direct,8),('NPG',npg,64)]}
    cfg=dict(tasks=tasks,profiles=profiles,algorithms=['CE','LSTD_PI','DIRECT_PI','NPG'],
        methods=['dense','known_rank','adaptive_1'],sensitivity_scenarios=['orth-exact','orth-tail010'],
        sensitivity_methods=['dense','known_rank','adaptive_0.5','adaptive_1','adaptive_2'],
        primary_methods=['dense','adaptive_1'],horizon=16,burn=1024,threads=2,solver_rtol=1e-8,
        solver_attempts=[[100,20],[200,20]],targets=[.1,.25,.5,1.],
        reporting='Fixed batch and updates; true J and absolute gap versus actual transitions; assigned budget endpoint and separate numerical/instability failures.',
        execution='Local, one worker; broad scenario screening first, then additional independent systems/trials and baseline budget profiles.')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
    total=sum(len(cfg['sensitivity_methods'] if t['scenario'] in cfg['sensitivity_scenarios'] else cfg['methods'])*4 for t in tasks)
    print(json.dumps(dict(scenarios=len(changes),task_profiles=len(tasks),algorithm_jobs=len(tasks)*4,trajectories=total)))


if __name__=='__main__':main()
