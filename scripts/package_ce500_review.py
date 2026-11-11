"""Compact review subset of a fully verified local CE500 dataset."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--bundles',type=Path,required=True)
    p.add_argument('--destination',type=Path,required=True);a=p.parse_args()
    assert read(a.bundles/'global-local-verification.json')['status']=='PASS'
    cost=read(a.bundles/'final-accounting/final_accounting_summary.json');assert cost['status']=='complete'
    assert read(a.bundles/'cost-local-verification.json')['status']=='PASS'
    chosen={}
    for path in (a.output/'report-confirm').iterdir():
        if path.is_file() and path.suffix in ('.csv','.json','.png','.svg'):chosen[a.output.name+'/'+str(path.relative_to(a.output)).replace('\\','/')]=path
    for rel in ['frozen/config.json','formal_plan.json','verification.json','preflight.json','artifact_sha256.json','execution_provenance.json',
                'documentation/CE500_FINDINGS_ZH.md','documentation/CE500_MATCHED_GAP_PROTOCOL_20261019.md',
                'documentation/ce100_reference_summary.json','identification-audit/audit.json',
                'frozen/scripts/ce500_matched_gap.py','frozen/scripts/rank_sweep100.py','frozen/dense_scaling.py',
                'frozen/release/scripts/ce500_identification_audit.py','frozen/release/scripts/ce500_execution_cost_audit.py']:
        chosen[a.output.name+'/'+rel]=a.output/rel
    for path in (a.bundles/'final-accounting').rglob('*'):
        if path.is_file():chosen[a.bundles.name+'/'+str(path.relative_to(a.bundles)).replace('\\','/')]=path
    for rel in ('global-local-verification.json','cost-local-verification.json'):
        chosen[a.bundles.name+'/'+rel]=a.bundles/rel
    assert all(p.is_file() for p in chosen.values())
    manifest={rel:sha(path) for rel,path in sorted(chosen.items())}
    with zipfile.ZipFile(a.destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for rel,path in sorted(chosen.items()):z.write(path,arcname=rel)
        z.writestr('REVIEW_FILE_SHA256.json',json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(a.destination) as z:
        assert z.testzip() is None
        for rel,digest in manifest.items():assert hashlib.sha256(z.read(rel)).hexdigest()==digest
    result=dict(status='PASS',review_zip=str(a.destination),archive_sha256=sha(a.destination),archive_bytes=a.destination.stat().st_size,
        review_files=len(manifest),full_dataset=str(a.output),full_dataset_global_manifest_sha256=sha(a.output/'artifact_sha256.json'),
        final_AMS_displayed_rounded_SU=cost['AMS_displayed_rounded_settled_SU_sum'],source_sha256=sha(Path(__file__)))
    (a.bundles/'review-package-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
