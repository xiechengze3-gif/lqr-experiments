"""Stdlib-only schedule/resource planning from an accepted saved R2 result."""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--population',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    assert not a.out.exists()
    for line in (ROOT/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);assert sha(ROOT/name)==digest
    config_path=ROOT/'config-X6b-protocol-v2.json'
    config=json.loads(config_path.read_text())
    data=json.loads(a.population.read_text(encoding='utf-8-sig'))
    assert data['status']=='POPULATION_READY' and data['new_primitive_transitions']==0
    assert data['source_sha256']==sha(ROOT/'population_only.py')
    assert data['core_sha256']==sha(ROOT/'population_core.py')
    assert data['engine_sha256']==sha(ROOT/'frozen_engine.py')
    assert data['config_sha256']==sha(config_path)
    rows=data['population']['rows'];selected=data['population']['selected_T']
    assert len(rows)==56
    for algorithm,key in [('NPG','population_NPG_T_grid'),('PI','population_PI_T_grid')]:
        qualified=[]
        for T in config[key]:
            subset=[r for r in rows if r['algorithm']==algorithm and r['T']==T]
            assert len(subset)==8 and len({(r['n'],r['system']) for r in subset})==8
            if all(r['stable'] and r['relative_gap']<=.05 for r in subset):qualified.append(T)
        assert qualified and selected[algorithm]==qualified[0]
    # Execute only the verified pure scalar scheduling function, without
    # importing NumPy/SciPy, the engine or any simulation on this machine.
    tree=ast.parse((ROOT/'actor_paths.py').read_text())
    function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='schedules')
    module=ast.Module(body=[function],type_ignores=[]);scope={'math':math}
    exec(compile(module,str(ROOT/'actor_paths.py'),'exec'),scope)
    schedules=scope['schedules']
    config.update(status='RESOLVED_FOR_RESOURCE_PILOT_NOT_FORMAL',
        selected_NPG_T=selected['NPG'],selected_PI_T=selected['PI'],
        population_result_sha256=sha(a.population),protocol_config_sha256=sha(config_path))
    resolved=[];jobs=[dict(component='equivalence',n=None,wall_minutes=5,cpus=1,memory_MiB=2048)]
    for n in config['n_values']:
        workload=baseline=0
        for rung in config['rungs']:
            batches=schedules(config['npg_bases'][str(n)],rung,selected['NPG'],selected['PI'])
            reference=schedules(config['npg_bases'][str(n)],rung,16,8)
            primitive=16*(sum(batches['NPG'])+17*selected['NPG'])
            assert primitive==16*(sum(batches['PI'])+17*selected['PI'])
            resolved.append(dict(n=n,rung=rung,batches=batches,primitive_per_arm_per_algorithm=primitive))
            workload+=max(batches['NPG'])+max(batches['PI'])
            baseline+=max(reference['NPG'])+max(reference['PI'])
        minutes=math.ceil(config['provisional_T16_resource_minutes'][str(n)]*workload/baseline)
        jobs.append(dict(component='timing-n'+str(n),n=n,wall_minutes=minutes,cpus=1,memory_MiB=2048))
    config['all_schedules']=resolved
    total=sum(j['wall_minutes'] for j in jobs)/60
    plan=dict(status='WITHIN_PROPOSED_RESOURCE_CAP' if total<=config['provisional_resource_pilot_cap_SU'] else 'OVER_RESOURCE_CAP_REVIEW_REQUIRED',
              experiment='X6b',stage='PILOT',jobs=jobs,requested_bound_SU=total,
              cap_SU=config['provisional_resource_pilot_cap_SU'],formal_submitted=False)
    a.out.mkdir(parents=True)
    (a.out/'resolved-config.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    plan['resolved_config_sha256']=sha(a.out/'resolved-config.json')
    (a.out/'resource-plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(selected_T=selected,resource_plan=plan,schedule_cells=len(resolved))))


if __name__=='__main__':main()
