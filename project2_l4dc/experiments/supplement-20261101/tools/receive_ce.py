import csv,json,math,tarfile
from collections import Counter
from pathlib import Path
from control import ROOT,sha,write,review

review();folder=ROOT/'X1';manifest=json.loads((folder/'ce-delivery-manifest.json').read_text())
transfer=json.loads((folder/'ce-delivery-transfer.json').read_text(encoding='utf-8-sig'))
assert sha(folder/'ce-delivery-v1.tar.gz')==manifest['archive_sha256']==transfer['sha256']
with tarfile.open(folder/'ce-delivery-v1.tar.gz') as tf:
    for member in tf.getmembers():
        assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
        path=ROOT/member.name;payload=tf.extractfile(member).read()
        if path.exists():assert path.read_bytes()==payload,'Never overwrite a previous result'
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(payload)
for item in manifest['files']:
    path=ROOT/item['relative'];assert path.stat().st_size==item['size'] and sha(path)==item['sha256']
old=json.loads((ROOT/'provenance/old_files_sha256.json').read_text())
assert all(sha(Path(p))==value for p,value in old.items())
dest=folder/'report-ce'
with (dest/'all_statistics.csv').open(newline='') as f:stats=list(csv.DictReader(f))
with (dest/'all_records.csv').open(newline='') as f:raw=list(csv.DictReader(f))
assert len(raw)==1728 and len(stats)==162
failed=Counter((r['mode'],r['N']) for r in raw if r['stable']=='False')
lookup={(float(r['null_scale']),int(r['m']),int(r['N']),r['mode'],r['metric']):r for r in stats}
def fmt(v):return f'{float(v):.6g}'
def interval(r):return f"{fmt(r['median'])} [{fmt(r['q25'])}, {fmt(r['q75'])}]"
body='Scope: **X1 CE only**. Actor R3 pilot is still in progress and actor formal remains gated.\n\n'
body+='All288 continuous formal trajectories and1728 outputs are delivered. '
body+='**15 unstable outputs are retained**, not rerun/deleted. Breakdown by method and regression prefix:\n\n'
body+='| Method | N | Failed outputs |\n|---|---:|---:|\n'
for (mode,N),count in sorted(failed.items()):body+=f'| {mode} | {N} | {count} |\n'
body+='\nMain point N8192 (8704 total transitions), medians [IQR]; m2 is the separate zero-null baseline.\n\n'
body+='| m | null | Method | Absolute gap | Relative gap | True redundant D | Stable |\n|---:|---:|---|---|---|---|---:|\n'
for m in [2,4,6,9,12]:
    alpha=0. if m==2 else .25
    for mode in ['dense','truncated']:
        g=lookup[(alpha,m,8192,mode,'gap')];rel=lookup[(alpha,m,8192,mode,'relative_gap')];d=lookup[(alpha,m,8192,mode,'redundant_cost')]
        body+=f"| {m} | {alpha} | {mode} | {interval(g)} | {interval(rel)} | {interval(d)} | {g['stable_count']}/32 |\n"
body+='\nFull zero-null control, both N, oracle diagnostic and system-bootstrap intervals are in the CSV tables. '
body+='Only paired same-system/seed/budget comparisons are called gains; finite-pair intervals do not replace failure-inclusive statistics.\n\n'
report=json.loads((dest/'REPORT.json').read_text())
body+=f"Independent saved-candidate check: {report['candidate_policies_independently_checked']} candidate policies; maximum normalized discrepancy between gap identities {report['max_normalized_gap_identity_error']:.3g}. "
body+='128 earlier X0 files plus the old experiment delivery remain unchanged; all178 protected older delivery files were byte-checked again.\n\n'
body+='Paths relative to this channel folder:\n\n'
for name in ['ce_main.png','ce_main.svg','ce_scaled_redundant_cost.png','ce_scaled_redundant_cost.svg','all_statistics.csv','all_records.csv','paired_ratios.csv','system_bootstrap_effects.csv','system_certificates.csv','REPORT.json']:
    body+=f'- `experiments/supplement-20261101/X1/report-ce/{name}`\n'
body+='\nSource config/hash: `configs/X1_v1.json`, `release-manifest-X1-v1.json`; CE approval: `X1/ACCEPTED_CE.json`; report source: `report_ce.py`. '
body+=f"Engine SHA256 `{report['source_hashes']['engine']}`, report SHA256 `{report['source_hashes']['report']}`. "
body+='Complete local delivery manifest: `X1/ce-delivery-manifest.json` (1196 files; includes original records and all candidate archives).\n\n'
body+='Interpretation limits: the finite N grid is not a budget-to-epsilon experiment; initial K0 geometry is disclosed (zero-null K0 is rank1 inside the true action subspace); '
body+='the m=r baseline does not match the nonzero-null initial cost. Formal CE failures despite stable pilots are retained and do not numerically certify the theorem constants. '
body+='No paper TeX or earlier result was changed.\n'
(folder/'ce_report_reply.md').write_text(body,encoding='utf-8')
write(folder/'CE_DELIVERY_VERIFIED.json',dict(status='PASS',files=manifest['count'],bytes=manifest['bytes'],raw_outputs=1728,unstable_outputs=15,old_files_unchanged=len(old)))
print(json.dumps({'delivery':'PASS','files':manifest['count'],'outputs':1728,'failed_outputs_by_mode_N':{str(k):v for k,v in failed.items()},'reply_prepared':str(folder/'ce_report_reply.md')},indent=2))
