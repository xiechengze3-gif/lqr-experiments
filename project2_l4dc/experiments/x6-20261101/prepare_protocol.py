"""Local stdlib-only preparation; never simulates, submits or edits old results."""
import ast
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'supplement-20261101'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    engine=ROOT/'frozen_engine.py'
    if not engine.exists():
        shutil.copyfile(OLD/'engine.py',engine)
    assert sha(engine)=='9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989'
    config=dict(experiment='X6a',version=1,n_values=[24,36,48,72],rank=2,
                blocks=[2048,8192,32768,131072,524288],horizon=dict(S=16,U=32),
                nu=1.,burn_blocks=16,ce_burn=512,formal_seeds=[1601,1602,1603,1604],
                calibration_seeds=[9601,9602,9603,9604],resource_seed=9701,
                formal_systems=dict(S=list(range(301,309)),U=list(range(401,409))),
                calibration_systems=dict(S=[9101,9102],U=[9201,9202]),
                formal_U_selection=None,study_requested_cap_SU=400,
                provisional_X6a_requested_ceiling_SU=23,
                resource_wall_minutes=15,resource_cpus=1,resource_memory_MiB=2048,
                formal_concurrency=32,implicit_retry_count=0)
    config['resource_tasks']=[]
    for family,system in [('S',9102),('U',9202)]:
        for n in config['n_values']:
            config['resource_tasks'].append(dict(cells=[dict(
                role='resource',family=family,n=n,system=system,seed=9701)]))
    config['formal_tasks']=[]
    for role,registry,seeds in [('formal','formal_systems',config['formal_seeds']),
                               ('calibration','calibration_systems',config['calibration_seeds'])]:
        for index in range(len(config[registry]['S'])):
            for seed in seeds:
                cells=[dict(role=role,family=family,n=n,
                            system=config[registry][family][index],seed=seed)
                       for family in ['S','U'] for n in config['n_values']]
                config['formal_tasks'].append(dict(role=role,system_index=index,cells=cells))
    path=ROOT/'config-X6a-v1.json'
    assert not path.exists(), 'Frozen config exists; make an explicitly reviewed new version.'
    path.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8',newline='\n')
    files=['frozen_engine.py','estimation.py','prepare_protocol.py',
           'config-X6a-v1.json','PROTOCOL_X6a_v1.md']
    for name in files:
        if name.endswith('.py'):
            ast.parse((ROOT/name).read_text(encoding='utf-8-sig'),filename=name)
    manifest={name:sha(ROOT/name) for name in files}
    (ROOT/'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name,digest in manifest.items()),
                                  encoding='utf-8',newline='\n')
    print(json.dumps(dict(status='AST_AND_CONFIG_ONLY_NO_NUMERICAL_RUN',hashes=manifest,
                         resource_tasks=len(config['resource_tasks']),
                         formal_tasks=len(config['formal_tasks']),
                         formal_cells=sum(len(x['cells']) for x in config['formal_tasks']))))

if __name__=='__main__':
    main()
