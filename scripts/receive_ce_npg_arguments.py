"""Verify and unpack only the small report archive into the E: workspace."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
NAME='ce-npg-arguments-20261028'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--sha256',required=True)
    ap.add_argument('--archive',default='report-delivery.tar.gz',choices=['report-delivery.tar.gz','report-delivery-reviewed.tar.gz'])
    args=ap.parse_args()
    target=(ROOT/'local_runs'/NAME).resolve();archive=target/args.archive
    assert target.is_relative_to(ROOT.resolve()) and archive.is_file()
    assert digest(archive)==args.sha256.lower(),'Archive SHA256 mismatch'
    with tarfile.open(archive,'r:gz') as stream:
        members=stream.getmembers()
        assert len(members)<500 and sum(m.size for m in members)<150*1024**2
        for member in members:
            resolved=(target/member.name).resolve()
            assert resolved.is_relative_to(target) and (member.isdir() or member.isfile()),member.name
            assert member.name.split('/')[0] in ['report','resource-plan.json','preflight.json','reuse-audit.json',
                'submission-preflight.json','submission-formal.json','submission-report.json','accounting.json',
                'scheduler-amendment.json','submission-report-recovery.json','submission-visual-review.json'],member.name
        kwargs={'filter':'data'} if hasattr(tarfile,'data_filter') else {}
        stream.extractall(target,members=members,**kwargs)
    checks={}
    for line in (target/'report'/'SHA256SUMS').read_text().splitlines():
        expected,name=line.split('  ',1);path=(target/'report'/name).resolve()
        assert path.parent==target/'report' and path.is_file()
        checks[name]=digest(path)==expected
    assert checks and all(checks.values()),'Individual report hash mismatch'
    summary=json.loads((target/'report'/'summary.json').read_text())
    assert summary['status']=='PASS' and summary['new_trajectories']==1728 and summary['reused_trajectories']==336
    for name in ['figure1_learning_dimension','figure2_redundant_mechanism','figure3_fullrank_adaptive']:
        assert checks[name+'.png'] and checks[name+'.svg']
    receipt=dict(status='PASS',archive_sha256=args.sha256,verified_report_files=len(checks),checks=checks,
        local_root=str(target),new_trajectories=1728,reused_trajectories=336,
        remote_root='/scratch/user/changze/lqr_experiments/results/'+NAME,
        full_raw_trajectories_downloaded=False,report_version=summary.get('report_version',1),
        learning_replayed=summary.get('learning_replayed',False),figure_visual_review='PENDING')
    (ROOT/'receipts'/(NAME+'-local-verification.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
