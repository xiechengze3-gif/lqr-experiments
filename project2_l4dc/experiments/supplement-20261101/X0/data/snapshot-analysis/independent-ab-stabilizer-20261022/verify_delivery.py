"""Saved-record and frozen-source checks; no simulation or numerical solves."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent


def pure_function(path,name):
    tree=ast.parse(path.read_text(encoding='utf-8'))
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    namespace={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
    return namespace[name]


def main():
    raw=(OUT/'construction.json').read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    assert digest=='d17806d41f9696562a0accebcb874fb9651db2e8e99e4855e90a5ac93b388f32'
    data=json.loads(raw);assert data['status']=='PASS' and data['job']=='20251912'
    expected={(n,4,s) for n in (50,100) for s in (5001,5002)}|{(500,r,5001) for r in (2,4,8,32,500)}
    assert {(r['n'],r['rank'],r['seed']) for r in data['systems']}==expected
    for row in data['systems']:
        assert row['status']=='PASS' and abs(row['rho_A']-1.05)<1e-10
        assert 0<row['rho_F0']<1-1e-10 and not row['uses_Kstar']
        assert not row['uses_cost_matrices'] and not row['gap_matching']
        assert row['A_B_independent_by_construction'] and row['initial_gap']>0
        assert row['lyapunov_relative_residual']<1e-8
    assert len({r['A_array_sha256'] for r in data['systems'] if r['n']==500})==1
    package=ROOT/'packages/independent-ab-studies-20261022-v1'
    source_count=0
    for line in (package/'SHA256SUMS').read_text().splitlines():
        expected_hash,relative=line.split('  ',1)
        assert hashlib.sha256((package/relative).read_bytes()).hexdigest()==expected_hash
        assert (ROOT/relative).read_bytes().replace(b'\r\n',b'\n')==(package/relative).read_bytes()
        source_count+=1
    generator_sha=hashlib.sha256((package/'scripts/independent_ab_stabilizer.py').read_bytes()).hexdigest()
    assert all(r['source_sha256']==generator_sha for r in data['systems'])
    tree=ast.parse((package/'scripts/independent_ab_stabilizer.py').read_text())
    init=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='initial_gain')
    assert [n.arg for n in init.args.args]==['a','b','rank','seed','prior_scale','pole_scale']
    called={n.func.id for n in ast.walk(init) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
    assert called <= {'rng','schur','int','dict','place_poles','str','float','ArithmeticError','len'}
    st=json.loads((package/'configs/stein_independent_stabilizer_20261022.json').read_text())
    ce=json.loads((package/'configs/ce500_independent_stabilizer_20261022.json').read_text())
    tasks=pure_function(package/'scripts/stein_independent_stabilizer.py','tasks')
    operations_tasks=pure_function(package/'scripts/independent_ab_operations.py','stein_tasks')
    for phase,number in [('pilot',16),('confirm',96)]:
        numerical=tasks(st,phase);scheduler=operations_tasks(st,phase)
        assert len(numerical)==len(scheduler)==number
        assert [{k:r[k] for k in ('n','seed','N','method')} for r in numerical]==scheduler
    assert st['H']==256 and st['algorithms']==['PI']
    assert len(ce['ranks'])*len(ce['confirm_seeds'])==150
    assert ce['absolute_targets']==[1.,.5,.1,.05] and 'initial_gap' not in ce
    result=dict(status='PASS',construction_sha256=digest,systems_checked=9,
        sources_checked=source_count,stable_initializers=9,
        rho_A=1.05,maximum_rho_F0=max(r['rho_F0'] for r in data['systems']),
        initializer_uses_Kstar=False,initializer_uses_cost_matrices=False,
        policy_initialization='May use the already drawn A/B solely for stabilization; no objective calibration.',
        Stein_PI_pilot_paths=16,Stein_PI_formal_paths=96,CE_formal_paired_datasets=150,
        scheduler_and_actor_task_maps_identical=True)
    (OUT/'delivery_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
