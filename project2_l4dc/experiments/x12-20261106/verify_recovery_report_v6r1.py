"""Verify report member bytes and acceptance invariants; no recomputation."""
import csv
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath

from virtual_task_store_v2 import file_sha


def load(p):
    return json.loads(p.read_bytes())


def count(p):
    with p.open(encoding='utf-8-sig',newline='') as f:
        return sum(1 for _ in csv.DictReader(f))


def main():
    r=Path(__file__).resolve().parent
    delivery=r/'delivery-recovery-report-v6r1'
    seal=load(delivery/'REMOTE_SEAL_ACCOUNTING.json')
    final=load(delivery/'recovery-report-DONE.json')
    coverage=load(r/'RECOVERY_FORMAL_COVERAGE_v6r1.json')
    assert final['status']=='X12_RECOVERY_REPORT_ARCHIVE_COMPLETE'
    assert final['config_sha256']==coverage['config_sha256'] and final['job']==seal['job']
    assert final['new_training_transitions']==0
    for n,m in seal['files'].items():
        assert (delivery/n).stat().st_size==m['bytes'] and file_sha(delivery/n)==m['sha256']
    a=delivery/'recovery-report-v5.tar.gz'
    assert a.stat().st_size==final['archive_bytes'] and file_sha(a)==final['archive_sha256']
    out=delivery/'report';out.mkdir()
    expected={m['path']:m for m in final['files']}
    assert len(expected)==len(final['files'])
    with tarfile.open(a,'r:gz') as tf:
        members=tf.getmembers()
        assert len(members)==len(expected) and {x.name for x in members}==set(expected)
        for member in members:
            name=PurePosixPath(member.name)
            assert member.isfile() and not name.is_absolute() and '..' not in name.parts
            assert ':' not in member.name and '\\' not in member.name
            data=tf.extractfile(member).read()
            assert len(data)==expected[member.name]['bytes'] and hashlib.sha256(data).hexdigest()==expected[member.name]['sha256']
            dest=out.joinpath(*name.parts)
            assert dest.resolve().is_relative_to(out.resolve())
            dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as f:f.write(data)
    x=r.parent/'x10-20261106'
    for name in ('summary_merged_nine_rungs.csv','transitions_saved_derived.csv','failures.csv','failure_counts_by_cell.csv'):
        merged='transitions_saved_merged_nine_rungs.csv' if name=='transitions_saved_derived.csv' else name
        assert (out/merged).read_bytes().startswith((x/name).read_bytes())
    assert count(out/'new-n60/summary.csv')==36 and count(out/'summary_merged_nine_rungs.csv')==180
    assert count(out/'transitions_saved_derived.csv')==2 and count(out/'transitions_saved_merged_nine_rungs.csv')==10
    assert count(out/'diagnostics-n60/endpoints.csv')==1152 and count(out/'diagnostics-n60/stages.csv')==14976
    proof=load(out/'ARCHIVE_COVERAGE_v5.json')
    assert proof['status']=='ALL_LOGICAL_RAW_ARCHIVE_MEMBERS_VERIFIED'
    assert proof['accepted_transitions']==coverage['training_transitions_by_origin']
    e=r/'delivery-recovery-tasks-v6r1'
    for t in proof['task_receipts']:
        local=load(e/f"{t['group']}-task-{t['index']:02d}.verified.json")
        assert local['archive_sha256']==t['archive_sha256'] and local['journal_sha256']==t['journal_sha256']
    acct=seal['accounting']
    assert len(acct['allocation_rows'])==143 and acct['actual_SU']<=230 and acct['exposure_SU']<=300
    assert acct['outstanding_upper_SU']==acct['report_reserved_SU']==0 and acct['no_double_counting_AMS']
    png=sorted(p.name for p in (out/'figures').glob('*.png'))
    assert png==['all_dimensions_gap.png','all_dimensions_relative_gap.png','n60_main_gap.png']
    result=dict(status='REPORT_ARCHIVE_AND_NUMERICAL_SCHEMA_VERIFIED_ON_E', archive_sha256=final['archive_sha256'],
                members=len(expected), exact_old_prefixes=True, report_job=seal['job'], total_actual_SU=acct['actual_SU'],
                historical_requested_SU=acct['historical_summed_requests_SU'], figures_to_review=png,
                endpoints=1152, stages=14976, scientific_analysis_unchanged=True, no_new_training_transitions=True)
    with (delivery/'VERIFIED_v6r1.json').open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2)
    print(json.dumps(result))


if __name__=='__main__':main()
