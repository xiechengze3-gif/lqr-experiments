"""Package measured X7 FORMAL under the17:30 conditional acceptance."""
import argparse,hashlib,io,json,re,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CHANNEL=ROOT.parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True)
    p.add_argument('--prepared',type=Path,required=True);p.add_argument('--exact-accepted-quote',required=True)
    a=p.parse_args();assert re.fullmatch(r'x7-20261102-formal-v\d+',a.name)
    protocol=json.loads((ROOT/'PROTOCOL_MANIFEST.json').read_text())
    for name,digest in protocol['files'].items():assert sha((ROOT/name).read_bytes())==digest,name
    task=(CHANNEL/'CLAUDE_TASK.md').read_bytes();text=task.decode('utf-8-sig');quote=a.exact_accepted_quote
    assert quote in text and all(word in quote for word in ['X7','PROTOCOL','ACCEPTED'])
    assert 'FORMAL is ACCEPTED in advance IF' in text and '<= 12 SU' in text and 'RSS headroom >= 20%' in text
    config=(a.prepared/'formal-config.json').read_bytes();cfg=json.loads(config)
    plan=(a.prepared/'formal-plan.json').read_bytes();resolved=json.loads(plan)
    proof=(ROOT/'RESOURCE_COMPLETE_v1.json').read_bytes();resource=json.loads(proof)
    assert cfg['status']=='FORMAL_FROZEN' and cfg['resource_complete_sha256']==sha(proof)
    assert resolved['formal_config_sha256']==sha(config) and resolved['requested_bound_SU']<=12
    assert resolved['maximum_RSS_KiB']<=.8*2048*1024 and resolved['projected_cumulative_requested_SU']<=15
    assert resource['status']=='COMPLETE_RESOURCE_ONLY'
    conditions=json.loads((ROOT/'FORMAL_CONDITIONS_MET.json').read_text())
    assert conditions['status']=='CONDITIONAL_FORMAL_ACCEPTANCE_SATISFIED'
    assert conditions['review_sha256']==sha(task) and conditions['formal_config_sha256']==sha(config)
    files={name:(ROOT/name).read_bytes() for name in protocol['files']}
    for name in ['PROTOCOL_MANIFEST.json','x7_resource_ops.py','x7_later_ops.py',
                 'build_formal_release.py','validate_formal_complete.py','accounting_x7.py',
                 'PILOT_REPORT.md','FORMAL_CONDITIONS_MET.json']:
        files[name]=(ROOT/name).read_bytes()
    files['PROTOCOL_SHA256SUMS']=(ROOT/'SHA256SUMS').read_bytes()
    files['formal-config.json']=config;files['formal-plan.json']=plan
    files['RESOURCE_COMPLETE_v1.json']=proof;files['CLAUDE_TASK_approved.md']=task
    approved=dict(experiment='X7',authorized_action='X7_FORMAL_CONDITIONAL',exact_quote=quote,
        task_sha256=sha(task),resource_proof_sha256=sha(proof),formal_config_sha256=sha(config),
        protocol_manifest_sha256=sha((ROOT/'PROTOCOL_MANIFEST.json').read_bytes()))
    files['approval.json']=(json.dumps(approved,indent=2)+'\n').encode()
    script='''#!/usr/bin/env bash
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$base/releases/__NAME__
cache=$base/cache/x7-20261102
temp=$base/tmp/x7-20261102/job-${SLURM_ARRAY_JOB_ID:?}-${SLURM_ARRAY_TASK_ID:?}
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B x7_driver.py formal --config formal-config.json --index "${SLURM_ARRAY_TASK_ID:?}"
'''.replace('__NAME__',a.name).encode()
    assert b'\r' not in script;files['run-formal.sbatch']=script
    hashes={name:sha(data) for name,data in files.items()}
    files['SHA256SUMS']=''.join(f'{digest}  {name}\n' for name,digest in hashes.items()).encode()
    archive=ROOT/'packages'/(a.name+'.tar.gz');assert not archive.exists()
    with tarfile.open(archive,'w:gz') as tf:
        for name,data in files.items():
            info=tarfile.TarInfo(name);info.size=len(data);tf.addfile(info,io.BytesIO(data))
    result=dict(status='BUILT_CONDITIONAL_FORMAL',name=a.name,archive=str(archive),
        archive_sha256=sha(archive.read_bytes()),hashes=hashes,plan=resolved,approval=approved)
    archive.with_suffix('.manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
