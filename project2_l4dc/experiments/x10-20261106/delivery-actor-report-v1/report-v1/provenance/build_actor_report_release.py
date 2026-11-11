"""Build the eight-SU saved-data report after whole-formal coverage proof."""
import argparse
import ast
import hashlib
import io
import json
import tarfile
from pathlib import Path

HERE=Path(__file__).resolve().parent.parent
CONTROL=HERE/'actor-correction-controls-v2'
CHANNEL=HERE.parents[1]
NAME='x10-20261106-b-report-v1'


def sha(data):return hashlib.sha256(data).hexdigest()


def encode(data):return (json.dumps(data,indent=2)+'\n').encode()


def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-review-sha256',required=True)
    args=p.parse_args()
    review=(CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert sha(review)==args.expected_review_sha256
    assert '### Report (both parts)' in review.decode('utf-8-sig')
    source=HERE/'prepared-actor-formal-v1'
    coverage_bytes=(HERE/'ACTOR_FORMAL_COVERAGE_v1.json').read_bytes()
    coverage=json.loads(coverage_bytes)
    assert coverage['status']=='FORMAL_COMPLETE_COVERAGE_SOURCES_COUNTS_RECEIPTS'
    assert coverage['bundles']==256 and coverage['paired_paths']==1280
    assert coverage['primitive_transitions']==243008280576
    assert coverage['config_sha256']==sha((source/'formal-config.json').read_bytes())
    files={}
    for line in (source/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        data=(source/name).read_bytes();assert sha(data)==digest
        files[name]=data
    for name in ['actor_report_products.py','render_actor_report.py','transfer_actor_report.py',
                 'copy_actor_provenance.py','submit_actor_report.py','actor_control.py','build_actor_report_release.py','accounting_actor.py']:
        selected=CONTROL/'render_report_v2.py' if name=='render_actor_report.py' else CONTROL/'transfer_report_v2.py' if name=='transfer_actor_report.py' else CONTROL/'submit_report_v3.py' if name=='submit_actor_report.py' else Path(__file__) if name=='build_actor_report_release.py' else HERE/name
        data=selected.read_bytes();ast.parse(data.decode(),filename=name);files[name]=data
    source_proof=json.loads((HERE/'actor-report-src-v1/COVERAGE_SOURCE_PROOF_v1.json').read_text())
    analyzer=(HERE/'actor-report-src-v1/analyze_actor_five_rungs.py').read_bytes()
    assert sha(analyzer)==source_proof['new_sha256']
    assert source_proof['original_sha256']==sha(files['analyze_actor.py'])
    files['analyze_actor_five_rungs.py']=analyzer
    files['COVERAGE_SOURCE_PROOF_v1.json']=(HERE/'actor-report-src-v1/COVERAGE_SOURCE_PROOF_v1.json').read_bytes()
    baseline=HERE/'actor-report-baseline-v1'
    baseline_proof=json.loads((baseline/'MANIFEST_v1.json').read_text())
    for name,digest in baseline_proof['files'].items():
        data=(baseline/name).read_bytes();assert sha(data)==digest
        files['paper_cross.py' if name=='paper_cross.py' else 'report-baseline/'+name]=data
    files['report-baseline/MANIFEST_v1.json']=(baseline/'MANIFEST_v1.json').read_bytes()
    dependency_bytes=(source/'OLD_REMOTE_DEPENDENCY_AUDIT_v2.json').read_bytes()
    dependency=json.loads(dependency_bytes)
    assert dependency['status']=='PASS_FORMAL_REPORT_NO_OLD_REMOTE_RESULT_DEPENDENCY'
    for path,digest in dependency['runtime_sources'].items():
        assert sha((HERE/path).read_bytes())==digest,path
    files['OLD_REMOTE_DEPENDENCY_AUDIT_v2.json']=dependency_bytes
    files['FORMAL_COVERAGE_v1.json']=coverage_bytes
    files['CLAUDE_TASK_REPORT_authorized.md']=review
    files['report-approval.json']=encode(dict(experiment='X10b',stage='REPORT',review_sha256=sha(review),
        exact_report_heading='### Report (both parts)',formal_proof_sha256=sha(coverage_bytes),
        formal_config_sha256=coverage['config_sha256'],requested_bound_SU=8,automatic_retries=0))
    template=(HERE/'actor-draft-v2/pilot-NPG.sbatch').read_text().replace('releases/x10-20261106-b-pilot-v1','releases/'+NAME)
    old='actor_pilot.py --config actor-config-protocol-v1.json --role NPG'
    assert template.count(old)==1
    for n in [72,48,36,24]:
        command=('analyze_actor_five_rungs.py inspect --config formal-config.json --n '+str(n)
                 +' --raw "$base/results/x10-20261106/X10b/formal-v1"'
                 +' --out "$base/results/x10-20261106/X10b/report-v1/diagnostics-n'+str(n)+'"')
        files['report-n'+str(n)+'.sbatch']=template.replace(old,command).encode()
    python='/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B '
    first=('analyze_actor_five_rungs.py summarize --config formal-config.json'
           +' --raw "$base/results/x10-20261106/X10b/report-v1"'
           +' --out "$base/results/x10-20261106/X10b/report-v1/new-rungs"')
    calls=first+'\n'+python+'actor_report_products.py --config formal-config.json\n'+python+'render_actor_report.py --config formal-config.json\n'+python+'copy_actor_provenance.py\n'+python+'transfer_actor_report.py pack --archive "$base/tmp/x10-20261106/x10b-report-v1.tar.gz"'
    files['report-aggregate.sbatch']=template.replace(old,calls).encode()
    hashes={name:sha(data) for name,data in files.items()}
    files['SHA256SUMS']=''.join(f'{digest}  {name}\n' for name,digest in hashes.items()).encode()
    archive=HERE/'packages'/(NAME+'.tar.gz');assert not archive.exists()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes()==review
    with tarfile.open(archive,'x:gz') as tf:
        for name,data in files.items():
            item=tarfile.TarInfo(name);item.size=len(data);tf.addfile(item,io.BytesIO(data))
    manifest=dict(status='REPORT_RELEASE_BUILT_NOT_SUBMITTED',name=NAME,archive=str(archive),
                  archive_sha256=sha(archive.read_bytes()),source_manifest_sha256=sha(files['SHA256SUMS']),files=hashes,
                  formal_proof_sha256=sha(coverage_bytes),formal_config_sha256=coverage['config_sha256'],review_sha256=sha(review),
                  requested_upper_SU=8,report_diagnostic_cpus=4,report_aggregate_cpus=1)
    with (HERE/'ACTOR_REPORT_MANIFEST_v1.json').open('x') as stream:json.dump(manifest,stream,indent=2)
    print(json.dumps({k:v for k,v in manifest.items() if k!='files'}))


if __name__=='__main__':main()
