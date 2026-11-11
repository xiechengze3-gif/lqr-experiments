"""Safely extract, verify every rank-4 scientific artifact, and recount N90."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import tarfile


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--bundles',type=Path,required=True)
    p.add_argument('--results-parent',type=Path,required=True);a=p.parse_args()
    name='ce500-rank4-extension-20261020';receipt=json.loads((a.bundles/'receipt.json').read_text(encoding='utf-8'))
    root=a.results_parent/name
    archive=a.bundles/'complete.tar';complete_downloaded=archive.exists()
    if complete_downloaded:
        assert archive.stat().st_size==receipt['complete_archive']['bytes']
        assert sha(archive)==receipt['complete_archive']['sha256']
        with tarfile.open(archive) as t:
            for m in t.getmembers():
                assert (a.results_parent/m.name).resolve().is_relative_to(root.resolve())
                assert not m.issym() and not m.islnk()
            t.extractall(a.results_parent,filter='data')
    else:
        data_receipt=json.loads((a.bundles/'data.json').read_text(encoding='utf-8'))
        for file,expected_size,expected_sha in [
            (a.bundles/'data.tar',data_receipt['bytes'],data_receipt['archive_sha256']),
            (a.bundles/'review.tar.gz',receipt['review_archive']['bytes'],receipt['review_archive']['sha256'])]:
            assert file.stat().st_size==expected_size and sha(file)==expected_sha,file
            with tarfile.open(file) as t:
                for m in t.getmembers():
                    assert (root/m.name).resolve().is_relative_to(root.resolve())
                    assert not m.issym() and not m.islnk()
                t.extractall(root,filter='data')
    manifest=root/'artifact_sha256.json';assert sha(manifest)==receipt['artifact_manifest_sha256']
    files=json.loads(manifest.read_text(encoding='utf-8'))
    if not complete_downloaded:
        for rel,expected in data_receipt['files'].items():assert files[rel]==expected,rel
    for rel,expected in files.items():
        assert (root/rel).resolve().is_relative_to(root.resolve())
        assert sha(root/rel)==expected,rel
    with (root/'report-confirm/sample_complexity.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    raw=[json.loads((root/'raw'/f'ce-r004-s{s:04d}.json').read_text(encoding='utf-8')) for s in range(200,230)]
    for row in [q for q in rows if q['rank']=='4']:
        target=float(row['relative_target']);hits=[]
        for budget in raw[0]['budgets']:
            wins=sum(any(q['method']==row['method'] and q['ols_samples']==budget and q['stable'] and q['relative_gap']<=target
                for q in r['records']) for r in raw)
            if wins>=27:hits.append(budget+256)
        expected=min(hits) if hits else None
        assert expected==(float(row['N_hat_90']) if row['N_hat_90'] else None),row
    audit=json.loads((root/'report-confirm/audit.json').read_text(encoding='utf-8'))
    assert audit['unique_policies_reevaluated']==900 and audit['final_joint_OLS_recomputed']==30
    result=dict(status='PASS',scientific_files_verified=len(files),rank4_N90_independently_recounted=4,
        raw_formal_seeds=len(raw),new_formal_policy_rechecks=900,
        complete_archive_downloaded=complete_downloaded,
        remote_complete_archive_sha256=receipt['complete_archive']['sha256'],
        verification_source_sha256=sha(Path(__file__)),
        artifact_manifest_sha256=sha(manifest),local_results=str(root))
    (a.bundles/'local-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
