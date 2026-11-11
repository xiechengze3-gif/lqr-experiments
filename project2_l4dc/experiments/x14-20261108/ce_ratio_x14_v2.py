"""Verify X10a CE pairs and apply the original Appendix H.2 readout locally."""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path


R=Path(__file__).resolve().parent
CE=R.parent/'x10-20261106/ce-formal-v2/dimension/n60'
REFERENCE=R.parent/'x6-20261101/CE-addition-v2'
GRID=(2048,8192,32768,131072,524288)
REPORT_SHA='a10aef06ec2c7c08a9b027d2f57b53f6ec9e8405f81892e9315acf23960a99da'
ENGINE_SHA='9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cover():
    rows={N:[] for N in GRID}
    evidence={}
    for system in range(301,309):
        for seed in range(1601,1605):
            folder=CE/f's{system}-t{seed}'
            done_bytes=(folder/'DONE.json').read_bytes()
            done=json.loads(done_bytes)
            assert done['status']=='COMPLETE' and done['spec']==dict(part='dimension',config='n60',system=system,seed=seed)
            assert done['engine_sha256']==ENGINE_SHA
            assert done['source_sha256']=='85708c342bd6b4229324e10688681b7be615460adf4fe77404a7f6f31c329465'
            manifest={a['N']:a for a in done['artifacts']}
            evidence[str((folder/'DONE.json').relative_to(CE))]=sha(done_bytes)
            for N in GRID:
                path=folder/f'prefix-{N}.json'
                data=path.read_bytes()
                prefix=json.loads(data)
                assert prefix['status']=='COMPLETE_PREFIX' and prefix['N']==N
                assert prefix['primitive_transitions']==N+512 and prefix['artifacts']==[a for a in done['artifacts'] if a['N']<=N]
                assert sha((folder/f'fit-{N}.npz').read_bytes())==prefix['fit_sha256']==manifest[N]['sha256']
                assert [r for r in done['records'] if r['N']<=N]==prefix['records']
                current=[r for r in prefix['records'] if r['N']==N]
                assert len(current)==2 and {r['arm'] for r in current}=={'dense','truncated'}
                pair=dict(system=system,seed=seed)
                for r in current:
                    assert (r['n'],r['m'],r['r'],r['algorithm'],r['system'],r['seed'],r['N'])==(60,60,2,'CE',system,seed,N)
                    assert r['primitive_transitions']==N+512 and math.isfinite(r['gap'])==r['stable']
                    pair[r['arm']+'_gap']=r['gap']
                    pair[r['arm']+'_stable']=r['stable']
                rows[N].append(pair)
                evidence[str(path.relative_to(CE))]=sha(data)
                evidence[str((folder/f'fit-{N}.npz').relative_to(CE))]=prefix['fit_sha256']
    assert all(len(group)==32 for group in rows.values()) and len(evidence)==352
    return rows,evidence


def frozen_functions(path, expected, names, env):
    data=path.read_bytes()
    assert sha(data)==expected
    module=ast.parse(data)
    nodes=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes}==set(names)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env)
    return env


def run():
    import csv
    import numpy as np

    rows,evidence=cover()
    saved=json.loads((R/'CE_COVERAGE_v1.json').read_bytes())
    assert saved['files']==evidence
    fn=frozen_functions(REFERENCE/'analyze_ce_gains.py',REPORT_SHA,('q','ratio','bootstrap'),dict(math=math))
    rng=frozen_functions(REFERENCE/'frozen_engine.py',ENGINE_SHA,('rng',),dict(np=np))['rng']
    out=[]
    for N,group in rows.items():
        valid=[fn['ratio'](r) for r in group if r['dense_stable'] and r['truncated_stable']]
        assert all(r is not None for r in valid)
        row=dict(family='S',n=60,m=60,N=N,primitive_per_arm=N+512,full_pairs=len(group),
                 dense_stable=sum(r['dense_stable'] for r in group),
                 truncated_stable=sum(r['truncated_stable'] for r in group),both_stable=len(valid),
                 paired_ratio_median=fn['q'](valid,.5))
        out.append(dict(row,**fn['bootstrap'](group,True,rng(620,1,60,N,1),5000)))
    with (R/'CE_ratio_n60.csv').open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)
    print(json.dumps(dict(status='COMPLETE_SAVED_DATA_ONLY',pairs=160,observation_transitions=0,
                          sha256=sha((R/'CE_ratio_n60.csv').read_bytes()))))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['coverage','readout'])
    if parser.parse_args().stage=='coverage':
        _,files=cover()
        with (R/'CE_COVERAGE_v1.json').open('x',encoding='utf-8') as f:
            json.dump(dict(status='ALL_160_SAVED_PAIRS_VERIFIED',files=files),f,indent=2)
        print('ALL_160_SAVED_PAIRS_VERIFIED')
    else:
        run()
