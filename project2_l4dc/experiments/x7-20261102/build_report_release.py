"""X7 frozen saved-data REPORT;conditionally accepted after full coverage."""
import argparse,hashlib,io,json,re,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CHANNEL=ROOT.parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True)
    p.add_argument('--prepared',type=Path,required=True);p.add_argument('--complete-proof',type=Path,required=True)
    p.add_argument('--exact-accepted-quote',required=True);a=p.parse_args()
    assert re.fullmatch(r'x7-20261102-report-v\d+',a.name)
    protocol=json.loads((ROOT/'PROTOCOL_MANIFEST.json').read_text())
    for name,digest in protocol['files'].items():assert sha((ROOT/name).read_bytes())==digest
    task=(CHANNEL/'CLAUDE_TASK.md').read_bytes();text=task.decode('utf-8-sig')
    quote=a.exact_accepted_quote
    assert quote in text and all(word in quote for word in ['X7','PROTOCOL','ACCEPTED'])
    assert 'REPORT (<= 2 SU) is ACCEPTED' in text
    config=(a.prepared/'formal-config.json').read_bytes()
    coverage=a.complete_proof.read_bytes();proof=json.loads(coverage)
    assert proof['status']=='COMPLETE_COVERAGE_COUNTS_SOURCES' and proof['config_sha256']==sha(config)
    assert proof['counts']==dict(tasks=32,paths=128,outputs=10752,fit_policy_archives=768,primitive_transitions=37814272)
    cfg=json.loads(config)
    jobs=[dict(component=f'diagnostics-n{n}-{spectrum}',n=n,spectrum=spectrum,
               tasks=1,cpus=1,memory_MiB=2048,wall_minutes=20,requested_bound_SU=1/3)
          for n in cfg['n_values'] for spectrum in cfg['spectra']]
    jobs.append(dict(component='summary',n=None,spectrum=None,tasks=1,cpus=1,
        memory_MiB=2048,wall_minutes=40,requested_bound_SU=2/3))
    assert abs(sum(row['requested_bound_SU'] for row in jobs)-2)<1e-9
    files={name:(ROOT/name).read_bytes() for name in protocol['files']}
    for name in ['PROTOCOL_MANIFEST.json','x7_resource_ops.py','x7_later_ops.py',
                 'build_report_release.py','accounting_x7.py','transfer_x7.py']:
        files[name]=(ROOT/name).read_bytes()
    files['PROTOCOL_SHA256SUMS']=(ROOT/'SHA256SUMS').read_bytes()
    files['formal-config.json']=config;files['FORMAL_COMPLETE_v1.json']=coverage
    files['RESOURCE_COMPLETE_v1.json']=(ROOT/'RESOURCE_COMPLETE_v1.json').read_bytes()
    files['CLAUDE_TASK_approved.md']=task
    approved=dict(experiment='X7',authorized_action='X7_REPORT_AFTER_FORMAL',exact_quote=quote,
        task_sha256=sha(task),resource_proof_sha256=sha(files['RESOURCE_COMPLETE_v1.json']),
        formal_config_sha256=sha(config),formal_complete_sha256=sha(coverage))
    files['approval.json']=(json.dumps(approved,indent=2)+'\n').encode()
    files['report-plan.json']=(json.dumps(dict(stage='REPORT',jobs=jobs,
        requested_bound_SU=2,zero_new_transitions=True,automatic_retries=0),indent=2)+'\n').encode()
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
py=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
case "$1" in
 diagnostics-n24-geometric|diagnostics-n24-polynomial|diagnostics-n48-geometric|diagnostics-n48-polynomial)
  part=${1#diagnostics-n};n=${part%%-*};spectrum=${part#*-}
  "$py" -B analyze_ce.py inspect --config formal-config.json --raw "$base/results/x7-20261102/formal-v1" --out "$base/results/x7-20261102/report-v1/$1" --n "$n" --spectrum "$spectrum"
  ;;
 summary)
  "$py" -B analyze_ce.py summarize --config formal-config.json --raw "$base/results/x7-20261102/report-v1" --out "$base/results/x7-20261102/report-v1/summary"
  "$py" -B transfer_x7.py pack --root "$base/results/x7-20261102" --scope formal --archive "$base/tmp/x7-20261102/x7-formal-v1.tar.gz"
  "$py" -B transfer_x7.py pack --root "$base/results/x7-20261102" --scope report --archive "$base/tmp/x7-20261102/x7-report-v1.tar.gz"
  ;;
 *) echo 'Unregistered report component' >&2;exit 2;;
esac
'''.replace('__NAME__',a.name).encode()
    assert b'\r' not in script;files['run-report.sbatch']=script
    hashes={name:sha(data) for name,data in files.items()}
    files['SHA256SUMS']=''.join(f'{digest}  {name}\n' for name,digest in hashes.items()).encode()
    archive=ROOT/'packages'/(a.name+'.tar.gz');assert not archive.exists()
    with tarfile.open(archive,'w:gz') as tf:
        for name,data in files.items():
            info=tarfile.TarInfo(name);info.size=len(data);tf.addfile(info,io.BytesIO(data))
    result=dict(status='BUILT_REPORT_AFTER_COMPLETE',name=a.name,archive=str(archive),
        archive_sha256=sha(archive.read_bytes()),hashes=hashes,approval=approved,jobs=jobs)
    archive.with_suffix('.manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
