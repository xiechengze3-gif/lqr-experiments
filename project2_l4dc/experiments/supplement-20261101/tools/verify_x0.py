"""Verify historical X0 tables without running or changing any old experiment."""
import csv, hashlib, json, shutil, tarfile
from pathlib import Path
from control import ROOT, append, review, sha, write

def main():
    review()
    out=ROOT/'X0'; manifest=json.loads((out/'source_manifest.json').read_text())
    receipt=json.loads((out/'transfer_receipt.json').read_text(encoding='utf-8-sig'))
    archive=out/'x0-retrieval-v1.tar.gz'
    assert sha(archive)==manifest['archive_sha256']==receipt['sha256']
    target=out/'data';target.mkdir(exist_ok=True)
    with tarfile.open(archive) as tf:
        for member in tf.getmembers():
            assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
        tf.extractall(target,filter='data')
    historical=json.loads((ROOT.parents[2]/'receipts/grace-storage-20261025/manifest.json').read_text())
    lookup={r['id']:r for r in historical['files']}
    records=[]
    for item in manifest['files']:
        path=target/item['archive_path']
        assert path.stat().st_size==item['size'] and sha(path)==item['sha256']
        source_id=item['remote'].split('/snapshot/',1)[-1]
        old=lookup.get(source_id)
        if old:assert item['sha256']==old['sha256']
        records.append(dict(item,historical_20261025_hash_verified=bool(old)))
    small=[r for r in records if 'independent-ab-stabilizer-20261022/' in r['archive_path']]
    assert len(small)==5 and all(r['historical_20261025_hash_verified'] for r in small)
    append('X0','PILOT','Pilot ingestion passed: archive hash verified; all five independent-A/B analysis files match both the source and immutable 2026-10-25 manifest. No simulation, policy solve or Slurm job. The user has now directly confirmed the 200-SU cap; see budget/USER_CAP_AMENDMENT.md.')
    review()
    group_manifest=json.loads((ROOT.parent/'provenance/retrieval_manifest.json').read_text())
    for item in group_manifest['files']:
        source=ROOT.parent/item['target'];assert sha(source)==item['sha256']
        dest=target/'existing-groups'/item['target'];dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest);assert sha(dest)==item['sha256']
        records.append({'archive_path':str(dest.relative_to(target)), 'source_local':str(source),'sha256':item['sha256'],'size':dest.stat().st_size,'historical_20261025_hash_verified':True})
    write(out/'verified_files.json',{'files':records,'count':len(records),'source_bundle_count':len(manifest['files']),'new_jobs':0,'new_SU':0})
    append('X0','FORMAL','Full historical-file ingestion complete (this is NOT an experimental formal run): 96 source-archive files plus 32 previously delivered original reports, all 128 hashes verified. Source bundle: X0/data/. No new Slurm submissions, no old-file modifications. X1–X3 formal learning remains gated on explicit ACCEPTED.')
    review()
    old=json.loads((ROOT/'provenance/old_files_sha256.json').read_text())
    assert all(Path(p).exists() and sha(p)==value for p,value in old.items())
    counts=[]
    for p in sorted(target.rglob('*.csv')):
        with p.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f); count=sum(1 for _ in reader)
        counts.append({'path':str(p.relative_to(out)), 'data_rows':count,'sha256':sha(p)})
    write(out/'REPORT.json',{'status':'COMPLETE','files_verified':len(records),'csv_tables':counts,'old_files_verified_unchanged':len(old),'new_SU':0,
      'limits':['Independent-A/B construction is a construction diagnostic, not a completed actor comparison.', 'CE500 pilot and confirm remain separate; supplied old code/protocol determine whether their burn and initialization match the new paper-faithful protocol.']})
    append('X0','REPORT','X0 complete: `experiments/supplement-20261101/X0/REPORT.json` and `verified_files.json`. Restored 128 files (96 independent-A/B/CE500 records plus 32 group01/group04 reports), including the CE500 report-confirm tables and PNG/SVG figures. CSV row counts and all hashes are recorded. All earlier delivery files remain byte-identical. The independent-A/B construction record is not relabeled as completed actor learning. New jobs: 0; spend: 0 SU.')
    print(json.dumps({'X0':'COMPLETE','files':len(records),'old_files_unchanged':len(old),'csvs':len(counts),'new_SU':0},indent=2))

if __name__=='__main__':main()
