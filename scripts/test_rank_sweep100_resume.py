"""Fault-injection checks: resume must preserve policies, RNG, failures and counts."""
import json
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
import rank_sweep100 as e


def main():
    cfg=e.read(e.ROOT/'configs/rank_sweep100_pilot_20261016.json')
    cfg.update(burn=7,eta=.005,sigma=2.,horizon=4,
               schedule_segments=[[1024,1],[2048,1],[4096,1]],ce_budgets=[512,1024,2048])
    base=e.ROOT/'.runtime'/'rank-sweep100-resume-tests-variable'
    base.mkdir(parents=True,exist_ok=True)
    checks=[];ident=e.identity(cfg)
    e.atomic_json(base/'test_config.json',cfg)
    for route,task in [('npg',e.npg_task),('ce',e.ce_task)]:
        reference=base/(route+'-uninterrupted');resumed=base/(route+'-interrupted')
        assert not list(reference.glob('raw/*.json')) and not list(resumed.glob('raw/*.json')),'Use a fresh test directory'
        task(cfg,8,9002,reference,ident)
        save=e.save_npz; interrupted=[False]
        def fault(path,**items):
            save(path,**items)
            if Path(path).parent.name=='checkpoints' and not interrupted[0]:
                interrupted[0]=True
                raise RuntimeError('Injected infrastructure interruption after atomic checkpoint')
        e.save_npz=fault
        try:
            task(cfg,8,9002,resumed,ident)
            raise AssertionError('Fault injection did not interrupt')
        except RuntimeError as error:
            assert 'Injected infrastructure' in str(error)
        finally:e.save_npz=save
        assert not list(resumed.glob('raw/*.json'))
        task(cfg,8,9002,resumed,ident)
        ref=e.read(next(reference.glob('raw/*.json')));actual=e.read(next(resumed.glob('raw/*.json')))
        if route=='npg':assert all(r['observed'] and r['stable'] for r in ref['records']), 'Test must exercise every learning stage'
        for key in ('records','physical_transitions'):assert ref[key]==actual[key],(route,key)
        if route=='npg':assert ref['algorithm_actual_transitions']==actual['algorithm_actual_transitions']
        with np.load(next(reference.glob('policies/*.npz'))) as a,np.load(next(resumed.glob('policies/*.npz'))) as b:
            for key in a.files:np.testing.assert_array_equal(a[key],b[key])
        checks.append(dict(route=route,status='PASS',bitwise_equal_policy_arrays=True,
                           records_identical=True,counts_identical=True,seed=9002))
    result=dict(status='PASS',checks=checks,scope='Excluded preflight seed; not included in experiment success denominators')
    e.atomic_json(base/'test_result.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    with threadpool_limits(limits=1):main()
