"""Freeze saved-data report controls and verify X10b exact-rank reuse."""
import ast
import csv
import hashlib
import io
import json
import tarfile
from pathlib import Path

from freeze_protocol import ROOT, X9, X10
from package_actor_x14 import REMOTE, PYTHON


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pack(stem, files):
    for name, data in files.items():
        if name.endswith('.py'):
            ast.parse(data, filename=name)
    hashes = {n:sha(b) for n,b in files.items()}
    out = ROOT/(stem+'.tar.gz')
    with tarfile.open(out,'x:gz') as tf:
        for name,data in files.items():
            entry = tarfile.TarInfo(name)
            entry.size=len(data)
            tf.addfile(entry,io.BytesIO(data))
    proof=dict(archive_sha256=sha(out.read_bytes()),files=hashes)
    with (ROOT/(stem+'.json')).open('x',encoding='utf-8') as f:
        json.dump(proof,f,indent=2)
    print(json.dumps(dict(stem=stem, **proof)))


def main():
    files={'submit_analysis_x14.py':(ROOT/'submit_analysis_x14.py').read_bytes(),
           'analysis-v1/report_actor_x14.py':(ROOT/'report_actor_x14.py').read_bytes(),
           'analysis-v1/x9-summary.csv':(X9/'summary.csv').read_bytes()}
    base = X9/'delivery-report-v1/report-v1'
    proof = json.loads((base/'verification.json').read_bytes())
    assert sha(files['analysis-v1/x9-summary.csv'])==proof['files']['summary.csv']
    for name in ('endpoints','new_stages','new_paired_endpoints','failures'):
        data=(base/(name+'.csv')).read_bytes()
        assert sha(data)==proof['files'][name+'.csv']
        files[f'analysis-v1/x9-{name}-header.csv']=data.splitlines(keepends=True)[0]
    merged = (X10/'summary_merged_nine_rungs.csv').read_bytes()
    proof10=json.loads((X10/'delivery-actor-report-v1/report-v1/PRODUCTS_COMPLETE_v1.json').read_bytes())
    assert sha(merged)==proof10['files']['summary_merged_nine_rungs.csv']
    x10 = [r for r in csv.DictReader(io.StringIO(merged.decode('utf-8-sig'))) if float(r['n'])==24]
    by={(r['algorithm'],float(r['rung']),r['ratio_kind']):dict(r,alpha='0.0',tau2_sq='0.0') for r in x10}
    for r in csv.DictReader(io.StringIO(files['analysis-v1/x9-summary.csv'].decode('utf-8-sig'))):
        if float(r['alpha'])==0:
            assert r==by[(r['algorithm'],float(r['rung']),r['ratio_kind'])]
    buffer=io.StringIO(newline='')
    writer=csv.DictWriter(buffer,fieldnames=list(x10[0]))
    writer.writeheader()
    writer.writerows(x10)
    files['analysis-v1/x10-n24-summary.csv']=buffer.getvalue().encode()
    for item in ('a','b'):
        script=f'''#!/bin/bash
set -euo pipefail
umask 077
r={REMOTE}
cd "$r"
sha256sum -c SHA256SUMS >/dev/null
export TMPDIR="$r/cache-report-${{SLURM_JOB_ID:?}}"
mkdir "$TMPDIR"
export TMP="$TMPDIR" TEMP="$TMPDIR" XDG_CACHE_HOME="$TMPDIR" NUMBA_CACHE_DIR="$TMPDIR/numba" MPLCONFIGDIR="$TMPDIR/mpl"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1 NUMBA_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONPATH="$r/source-v1"
exec {PYTHON} -B "$r/analysis-v1/report_actor_x14.py" {item} --root "$r"
'''
        files[f'{item}-report.sbatch']=script.encode()
    pack('analysis-x14-release-v1',files)


if __name__=='__main__':
    main()
