"""Freeze the eight missing B* rungs and exact non-60 reference bytes."""
import ast
import json
import math
import tarfile
from pathlib import Path

from package_actor_x14 import REMOTE, PYTHON
from package_report_x14 import pack, sha


R=Path(__file__).resolve().parent
X12=R.parent/'x12-20261106'
REVIEW='34d8f762f12971da5d82eb0863132f12c41acfe8695e4a272e1af2874332ab53'
TOP='4ed35bc55bdd33ece61ce829958baab956a31a1729ff636e01fec1f790e54475'


def main():
    review=(R.parents[1]/'CLAUDE_TASK.md').read_bytes()
    assert sha(review)==REVIEW
    section=review[review.index(b'## X14f extension GO:'):]
    package=R/'actor-f-x14-release-v1.tar.gz'
    assert sha(package.read_bytes())==TOP
    with tarfile.open(package,'r:gz') as tf:
        original={m.name.split('/',1)[1]:tf.extractfile(m).read() for m in tf.getmembers()}
    config=json.loads(original['config-x14f-v1.json'])
    actor=ast.parse(original['actor_paths.py'])
    function,=[n for n in actor.body if isinstance(n,ast.FunctionDef) and n.name=='schedules']
    env=dict(math=math)
    exec(compile(ast.Module(body=[function],type_ignores=[]),'X12 actor_paths.schedules','exec'),env)
    schedule=env['schedules']
    assert schedule(3276800,1,16,8)==config['all_schedules'][0]['batches']
    rungs=[1/2**j for j in range(8,0,-1)]
    entries=[]
    for rung,j in zip(rungs,range(8,0,-1),strict=True):
        batches=schedule(3276800,rung,16,8)
        M=16*(sum(batches['NPG'])+17*16)
        assert M==16*(sum(batches['PI'])+17*8)
        entries.append(dict(n=60,rung=rung,rung_label=f'Bstar-j{j}',batches=batches,
                            primitive_per_arm_per_algorithm=M))
    config.update(rungs=rungs,all_schedules=entries,npg_bases={'60':3276800},
                  formal_groups=[dict(id=f'n60-lower-{alg}',n=60,
                                      runs=[dict(algorithm=alg,rung=row['rung'],rung_label=row['rung_label'])
                                            for row in entries]) for alg in ('NPG','PI')])
    payload={name:original[name] for name in ('actor_paths.py','frozen_engine.py','estimation.py','analyze_actor.py',
              'virtual_task_store_v2.py','RESOURCE_HISTORY_FLOOR_X12.json')}
    payload.update({n:b for n,b in original.items() if n.startswith('models/')})
    for name in ('run_actor_x14f_full.py','x14f_full_ops.py','report_x14f_full.py'):
        payload[name]=(R/name).read_bytes()
    config['scientific_sources']['formal_driver.py']=sha(payload['run_actor_x14f_full.py'])
    payload['config-x14f-full-v1.json']=(json.dumps(config,indent=2)+'\n').encode()
    reference=X12/'delivery-recovery-report-v6r1/report'
    proof=json.loads((reference/'PRODUCTS_COMPLETE_v1.json').read_bytes())
    assert proof['job']=='20425741' and proof['new_summary_rows']==36
    for name,key in [('summary_merged_nine_rungs.csv','summary'),('transitions_saved_merged_nine_rungs.csv','transitions')]:
        data=(reference/name).read_bytes()
        assert sha(data)==proof['files'][name]
        payload[f'X12_merged_original_{key}.csv']=data
    total=sum(r['primitive_per_arm_per_algorithm'] for r in entries)
    protocol=section+b'\n\n## Frozen extension inputs\n\n'
    protocol+=(f'The eight lower rungs cost {total:,} primitive transitions per arm of each algorithm. '
               'The sealed X14f top rung is reused and relabelled as 1 relative to B*. '
               'The two pilot tasks each exercise all eight lower rungs on X12 pilot 9102/9801. '
               'One CPU, 2 GiB, 160 minutes upper per pilot. Use the same X12 historical resource floor '
               'with the pilot to choose the formal wall cap. Only overlap with the original top-rung '
               'array if total queue reservation remains within 64. Use the existing X14f ledger.\n\n'
               f'- Claude review `{REVIEW}`\n- Extension ruling `{sha(section)}`\n- X14f top release `{TOP}`\n').encode()
    protocol+=''.join(f'- `{n}` `{sha(b)}`\n' for n,b in payload.items()).encode()
    with (R/'PROTOCOL_X14f-full_v1.md').open('xb') as f:
        f.write(protocol)
    payload['PROTOCOL_X14f-full_v1.md']=protocol
    files={f'frozen-full-v1/{name}':data for name,data in payload.items()}
    for stage in ('pilot','formal','report'):
        run='report_x14f_full.py' if stage=='report' else f'run_actor_x14f_full.py {stage} "$SLURM_ARRAY_TASK_ID"'
        script=f'''#!/bin/bash
set -euo pipefail
umask 077
r={REMOTE}
cd "$r"
sha256sum -c frozen-f-v1/SHA256SUMS >/dev/null
sha256sum -c frozen-full-v1/SHA256SUMS >/dev/null
export TMPDIR="$r/cache-full-${{SLURM_JOB_ID:?}}-${{SLURM_ARRAY_TASK_ID:?}}"
mkdir "$TMPDIR"
export TMP="$TMPDIR" TEMP="$TMPDIR" XDG_CACHE_HOME="$TMPDIR" NUMBA_CACHE_DIR="$TMPDIR/numba" MPLCONFIGDIR="$TMPDIR/mpl"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$r:$r/frozen-f-v1"
exec {PYTHON} -B "$r/frozen-full-v1/"{run}
'''
        files[f'frozen-full-v1/f-full-{stage}.sbatch']=script.encode()
    files['frozen-full-v1/SHA256SUMS']=''.join(f'{sha(data)}  {name}\n' for name,data in files.items()).encode()
    pack('actor-full-x14-release-v1',files)


if __name__=='__main__':
    main()
