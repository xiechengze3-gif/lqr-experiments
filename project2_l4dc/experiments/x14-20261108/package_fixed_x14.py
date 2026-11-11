"""Verify X6a provenance and package X12 inputs without modifying the sources."""
import csv
import json
from pathlib import Path

from package_report_x14 import pack, sha
from package_actor_x14 import PYTHON, REMOTE


HERE=Path(__file__).resolve().parent
X12=HERE.parent/'x12-20261106'
A1=HERE.parent/'x6-20261101/amendment-A1'
ARCHIVE_SHA='2c897cbfe43890f315f391d7fd4db9d82d4332c5f0b9029d582b38b69b471483'


def get(path, expected):
    data=path.read_bytes()
    assert sha(data)==expected, path
    return data


def main():
    prior=A1/'deliveries/report-20365069-v4/X6a/reports/v1'
    proof=json.loads((prior/'verification.json').read_bytes())
    assert proof['status']=='COMPLETE' and proof['job']=='20365069'
    original={name:get(A1/name,proof[field]) for name,field in
              [('analyze_saved.py','source_sha256'),('estimation.py','collector_sha256'),('frozen_engine.py','engine_sha256')]}
    hashes={name:sha(data) for name,data in original.items()}
    for name in ('summary.csv','calibration.csv','observations.csv'):
        get(prior/name,proof['files'][name])
    with (prior/'summary.csv').open(newline='',encoding='utf-8') as f:
        old=list(csv.DictReader(f))
    registered={}
    for alg,counts,expected in [('NPG',(2**19,2**19,2**22,2**22),('2.34','2.64','3.47','4.00')),
                                ('PI',(2**19,2**19,2**22,2**22),('2.44','3.02','3.57','4.32')),
                                ('CE',(2**19,)*4,('2.46','3.04','3.57','4.26'))]:
        values=[]
        for n,N in zip((24,36,48,72),counts):
            row,=[r for r in old if r['family']=='S' and r['role']=='formal' and r['arm']=='dense'
                  and r['algorithm']==alg and int(r['n'])==n and int(r['N'])==N]
            values.append(row['paired_error_ratio_median'])
        assert tuple(f'{float(value):.2f}' for value in values)==expected, (alg,values)
        registered[alg]=values
    plan=dict(source_hashes=hashes,reference_report='20365069',reference_csv_sha256=proof['files'],
              table_writer_sha256=sha((A1/'write_report_v2.py').read_bytes()),
              reproduced_estimate_table=registered,pilot_source_archive_sha256=ARCHIVE_SHA)
    downloads=X12/'raw-downloads-v1'
    get(downloads/'x12-raw-calibration-v1.tar.gz',ARCHIVE_SHA)
    seal=json.loads((downloads/'x12-raw-calibration-v1.tar.json').read_bytes())
    assert seal['archive_sha256']==ARCHIVE_SHA and seal['scope']=='pilot-initial'
    paths={row['path']:row['sha256'] for row in seal['files']}
    raw=X12/'raw-deliveries-v1/calibration-v1'
    originals=dict(original)
    for i in range(8):
        task=f'calibration-v1/task-{i}'
        selected={k:v for k,v in paths.items() if k.startswith(task+'/')}
        assert len(selected)==10
        for name,digest in selected.items():
            originals[name.replace('calibration-v1/','pilot/',1)]=get(raw/name,digest)
    registry=X12/'formal-models-v1'
    registry_path=registry/'DONE.json'
    registry_receipt=json.loads(registry_path.read_bytes())
    assert registry_receipt['status']=='FORMAL_MODELS_FIXED_NO_OBSERVATIONS'
    assert registry_receipt['engine_sha256']==hashes['frozen_engine.py']
    assert registry_receipt['estimator_sha256']==hashes['estimation.py']
    models={v['path']:v['sha256'] for v in registry_receipt['models'].values()}
    assert set(models)=={f'n60-s{i}.npz' for i in range(301,309)}
    plan.update(formal_registry_sha256=sha(registry_path.read_bytes()),formal_models=models)
    originals['formal-models/DONE.json']=registry_path.read_bytes()
    for name,digest in models.items():
        originals['formal-models/'+name]=get(registry/name,digest)
    originals['inputs.json']=(json.dumps(plan,indent=2)+'\n').encode()
    for name in ('fixed_gain_x14.py','submit_fixed_x14.py'):
        originals[name]=(HERE/name).read_bytes()
    files={f'estimation-v1/{k}':v for k,v in originals.items()}
    for key,mode in [('c-pilot','calibration'),('d-pilot','pilot'),('d-formal','formal'),('d-report','report')]:
        script=f'''#!/bin/bash
set -euo pipefail
umask 077
r={REMOTE}
cd "$r"
sha256sum -c SHA256SUMS >/dev/null
sha256sum -c estimation-v1/SHA256SUMS >/dev/null
export TMPDIR="$r/cache-fixed-${{SLURM_JOB_ID:?}}"
mkdir "$TMPDIR"
export TMP="$TMPDIR" TEMP="$TMPDIR" XDG_CACHE_HOME="$TMPDIR" NUMBA_CACHE_DIR="$TMPDIR/numba" MPLCONFIGDIR="$TMPDIR/mpl"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$r:$r/source-v1"
exec {PYTHON} -B "$r/estimation-v1/fixed_gain_x14.py" {mode}
'''
        files[f'estimation-v1/{key}.sbatch']=script.encode()
    files['estimation-v1/SHA256SUMS']=''.join(f'{sha(data)}  {name}\n' for name,data in files.items()).encode()
    pack('fixed-x14-release-v1',files)


if __name__=='__main__':
    main()
