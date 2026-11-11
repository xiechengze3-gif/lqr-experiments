"""Build X9 REPORT only after full proof and a fresh read of its GO authorization."""
import argparse
import ast
import hashlib
import io
import json
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
NAME = 'x9-20261106-report-v1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--expected-review-sha256', required=True)
    a = p.parse_args()
    review = (CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert sha(review) == a.expected_review_sha256
    quote = 'Then REPORT as in X9 GO.'
    assert quote in review.decode('utf-8-sig')
    coverage_path = HERE/'FORMAL_COVERAGE_v1.json'
    coverage = json.loads(coverage_path.read_text())
    assert coverage['status'] == 'FORMAL_COMPLETE_COVERAGE_SOURCES_COUNTS_RECEIPTS'
    assert coverage['paired_paths'] == 1024 and coverage['bundles'] == 384
    config = (HERE/'prepared-formal-v1/formal-config.json').read_bytes()
    assert sha(config) == coverage['config_sha256']
    files = {}
    for line in (HERE/'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        payload = (HERE/name).read_bytes()
        assert sha(payload) == digest
        if name not in ['approval.json', 'run.sbatch']:
            files[name] = payload
    for name in ['render_report.py', 'transfer_report.py', 'audit_formal_x9.py',
                 'copy_report_provenance.py', 'submit_report_x9.py', 'build_report_release.py', 'accounting_x9.py']:
        payload = (HERE/name).read_bytes()
        ast.parse(payload.decode('utf-8'), filename=name)
        files[name] = payload
    files.update({'formal-config.json': config,
                  'formal-plan.json': (HERE/'prepared-formal-v1/formal-plan.json').read_bytes(),
                  'FORMAL_COVERAGE_v1.json': coverage_path.read_bytes(),
                  'PILOT_MANIFEST_v1.json': (HERE/'PILOT_MANIFEST_v1.json').read_bytes(),
                  'PILOT_REPORT_v1.md': (HERE/'PILOT_REPORT_v1.md').read_bytes(),
                  'CLAUDE_TASK_REPORT_authorized.md': review})
    approval = dict(experiment='X9', stage='REPORT', exact_report_quote=quote,
                    review_sha256=sha(review), formal_proof_sha256=sha(coverage_path.read_bytes()),
                    formal_config_sha256=sha(config), requested_upper_SU=2,
                    cumulative_requested_upper_SU=49.93333333333334)
    files['report-approval.json'] = (json.dumps(approval, indent=2)+'\n').encode()
    shell = '''#!/usr/bin/env bash
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$base/releases/x9-20261106-report-v1
cache=$base/cache/x9-20261106
temp=$base/tmp/x9-20261106/job-${SLURM_ARRAY_JOB_ID:?}-${SLURM_ARRAY_TASK_ID:?}
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
python=/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python
"$python" -B analyze_x9.py --config formal-config.json
"$python" -B render_report.py --config formal-config.json
"$python" -B copy_report_provenance.py
"$python" -B transfer_report.py pack --archive "$base/tmp/x9-20261106/x9-report-v1.tar.gz"
'''
    files['report.sbatch'] = shell.encode()
    hashes = {name: sha(payload) for name, payload in files.items()}
    files['SHA256SUMS'] = ''.join(f'{digest}  {name}\n' for name, digest in hashes.items()).encode()
    target = HERE/'packages'/(NAME+'.tar.gz')
    assert not target.exists()
    assert sha((CHANNEL/'CLAUDE_TASK.md').read_bytes()) == a.expected_review_sha256
    with tarfile.open(target, 'x:gz') as tf:
        for name, payload in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            tf.addfile(member, io.BytesIO(payload))
    manifest = dict(status='REPORT_RELEASE_BUILT_NOT_SUBMITTED', name=NAME,
                    archive=str(target), archive_sha256=sha(target.read_bytes()),
                    approval=approval, files=hashes, source_manifest_sha256=sha(files['SHA256SUMS']))
    with target.with_suffix('.manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}))


if __name__ == '__main__':
    main()
