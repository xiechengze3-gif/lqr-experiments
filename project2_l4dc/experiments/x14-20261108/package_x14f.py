"""Freeze the X14f ruling, the sole new rung, and the unchanged X12 sources."""
import ast
import json
import math
from pathlib import Path

from package_actor_x14 import REMOTE, PYTHON
from package_report_x14 import pack, sha


R=Path(__file__).resolve().parent
X12=R.parent/'x12-20261106'
REVIEW='a53fe7ee42848bef9c5b4e36d51d9f7c30cdaa5ff76f573833338a4a255e0d82'
X12_CONFIG='194f34ba2af8bd822396a9ae1e2317219ee5beb2da4f9a54df1d3eb479097d14'
ANALYZER='0e6e8291c573a6f3a6f491d135d91ddcfef1b7144f125004ad2d6bdb63d14b72'
CROSS='d07e548f861e7edf4191c9735015553706d012dfca2077adc7b5d212ea9e5a8e'


def checked(path,expected):
    data=path.read_bytes()
    assert sha(data)==expected,path
    return data


def main():
    channel=checked(R.parents[1]/'CLAUDE_TASK.md',REVIEW)
    start=channel.index(b'## X14f GO: n = 60 at a budget in line with n(n+m)')
    ruling=channel[start:]
    source=X12/'formal-release-v1'
    base=checked(source/'formal-config.json',X12_CONFIG)
    config=json.loads(base)
    registered=config['scientific_sources']
    assert config['rungs'][-1]==1 and config['npg_bases']=={'60':2**21}
    assert config['selected_NPG_T']==16 and config['selected_PI_T']==8
    payload={name:checked(source/name,registered[name]) for name in ('actor_paths.py','frozen_engine.py','estimation.py')}
    payload['analyze_actor.py']=checked(source/'analyze_actor.py',ANALYZER)
    payload['paper_cross.py']=checked(source/'paper_cross.py',CROSS)
    payload['report_products_v1.py']=(X12/'report_products_v1.py').read_bytes()
    payload['X12_formal_config_readonly.json']=base
    task_store=(X12/'virtual_task_store_v2.py').read_bytes()
    assert sha(task_store)=='73fb86e75df141b4ce89c901f9b450b1cccb71dcb33db2aad8e926addc91250c'
    payload['virtual_task_store_v2.py']=task_store
    for name in ('run_actor_x14f.py','x14f_ops.py','report_x14f.py'):
        payload[name]=(R/name).read_bytes()
    cost=json.loads((X12/'PILOT_COST_GATES_v1.json').read_bytes())
    payload['RESOURCE_HISTORY_FLOOR_X12.json']=checked(X12/'RESOURCE_HISTORY_FLOOR_v1.json',cost['resource_floor_sha256'])
    reference=X12/'delivery-recovery-report-v6r1/report/new-n60'
    proof=json.loads((reference/'verification.json').read_bytes())
    assert proof['job']=='20425741' and proof['paired_cells']==36 and proof['source_sha256']==ANALYZER
    payload['X12_n60_nine_rungs_summary.csv']=checked(reference/'summary.csv',proof['files']['summary.csv'])
    for meta in config['model_registry'].values():
        path=Path(meta['path'])
        assert path.parent.as_posix()=='models'
        payload[path.as_posix()]=checked(X12/'formal-models-v1'/path.name,meta['sha256'])
    tree=ast.parse(payload['actor_paths.py'])
    schedules,=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='schedules']
    env=dict(math=math)
    exec(compile(ast.Module(body=[schedules],type_ignores=[]),'X12 actor_paths.schedules','exec'),env)
    make=env['schedules']
    assert all(row['batches']==make(2**21,row['rung'],16,8) for row in config['all_schedules'])
    rung=1.5625
    assert (2**21)*rung==3276800
    label='r15625'
    batches=make(2**21,rung,16,8)
    M=(sum(batches['NPG'])+17*16)*16
    assert M==(sum(batches['PI'])+17*8)*16
    original_config_sha=sha(base)
    config.update(rungs=[rung],all_schedules=[dict(n=60,rung=rung,rung_label=label,batches=batches,
                  primitive_per_arm_per_algorithm=M)],timing_system=9102,timing_seed=9801,
                  post_hoc_budget_blocks=3276800,x12_original_config_sha256=original_config_sha)
    config['formal_groups']=[dict(id='n60-one-'+alg,n=60,runs=[dict(algorithm=alg,rung=rung,rung_label=label)])
                             for alg in ('NPG','PI')]
    registered.update({'formal_driver.py':sha(payload['run_actor_x14f.py']),'analyze_actor.py':ANALYZER})
    config_bytes=(json.dumps(config,indent=2)+'\n').encode()
    payload['config-x14f-v1.json']=config_bytes
    hashes={name:sha(data) for name,data in payload.items()}
    protocol=ruling+b'\n\n## Frozen X14f inputs and execution\n\n'
    protocol+=(f'Primitive transitions per arm and algorithm {M:,}, with identical integer budgets. '
               'Timing uses the X12 pilot system 9102 and seed 9801, one two-arm path per algorithm, '
               'one CPU and 2 GiB, with a 160 minute upper request. The measured bodies and the original '
               'X12 historical per-transition floors gate the 64-task formal array. All formal models '
               'retain their original X12 bytes. Training, summary and cross functions retain their original '
               'source bytes. The report sets the X12 crossing rung-count guard and metadata to ten. '
               'A separate archive adapter supplies raw paths.\n\n'
               f'- Claude review `{REVIEW}`\n- X14f ruling `{sha(ruling)}`\n').encode()
    protocol+=''.join(f'- `{name}` `{digest}`\n' for name,digest in hashes.items()).encode()
    with (R/'PROTOCOL_X14f_v1.md').open('xb') as f:
        f.write(protocol)
    payload['PROTOCOL_X14f_v1.md']=protocol
    files={f'frozen-f-v1/{name}':data for name,data in payload.items()}
    for stage in ('pilot','formal','report'):
        run='report_x14f.py' if stage=='report' else f'run_actor_x14f.py {stage} "$SLURM_ARRAY_TASK_ID"'
        script=f'''#!/bin/bash
set -euo pipefail
umask 077
r={REMOTE}
cd "$r"
sha256sum -c frozen-f-v1/SHA256SUMS >/dev/null
export TMPDIR="$r/cache-f-${{SLURM_JOB_ID:?}}-${{SLURM_ARRAY_TASK_ID:?}}"
mkdir "$TMPDIR"
export TMP="$TMPDIR" TEMP="$TMPDIR" XDG_CACHE_HOME="$TMPDIR" NUMBA_CACHE_DIR="$TMPDIR/numba" MPLCONFIGDIR="$TMPDIR/mpl"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$r"
exec {PYTHON} -B "$r/frozen-f-v1/"{run}
'''
        files[f'frozen-f-v1/f-{stage}.sbatch']=script.encode()
    files['frozen-f-v1/SHA256SUMS']=''.join(f'{sha(data)}  {name}\n' for name,data in files.items()).encode()
    pack('actor-f-x14-release-v1',files)


if __name__=='__main__':
    main()
