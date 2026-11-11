"""Retrieve verified normalized reports into E: without any simulator dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
NAME='ce-npg-initial-gap-20261028'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--sha256',required=True);args=ap.parse_args()
    target=(ROOT/'local_runs'/NAME).resolve();archive=target/'delivery.tar.gz'
    assert target.is_relative_to(ROOT.resolve()) and sha(archive)==args.sha256
    with tarfile.open(archive,'r:gz') as stream:
        members=stream.getmembers()
        assert len(members)<200 and sum(m.size for m in members)<150*1024**2
        for member in members:
            assert (target/member.name).resolve().is_relative_to(target)
            assert member.isdir() or member.isfile()
            assert member.name.split('/')[0] in ['report','submission.json','accounting.json']
        kwargs={'filter':'data'} if hasattr(tarfile,'data_filter') else {}
        stream.extractall(target,members=members,**kwargs)
    checks={}
    for line in (target/'report/SHA256SUMS').read_text(encoding='ascii').splitlines():
        expected,name=line.split('  ',1);path=(target/'report'/name).resolve()
        assert path.parent==target/'report' and path.is_file()
        checks[name]=sha(path)==expected
    assert checks and all(checks.values())
    summary=json.loads((target/'report/summary.json').read_text(encoding='utf-8'))
    assert summary['status']=='PASS' and summary['new_learning_runs']==0 and summary['new_training_transitions']==0
    assert summary['input_rows']==96600 and summary['all_NPG_unstable_paths_retained']==228
    assert summary['original_absolute_budget_rows_reproduced_exactly']==144
    pngs=sorted(name for name in checks if name.endswith('.png'));assert len(pngs)==13
    receipt=dict(status='PASS',archive_sha256=args.sha256,verified_report_files=len(checks),checks=checks,
        PNG_count=len(pngs),figure_visual_review='PENDING',new_learning_runs=0,new_training_transitions=0,
        new_control_solves=0,old_absolute_budget_rows_reproduced=144,old_inputs_unchanged=summary['original_inputs_unchanged'],
        local_root=str(target),remote_root='/scratch/user/changze/lqr_experiments/results/'+NAME)
    (ROOT/'receipts'/(NAME+'-local-verification.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
