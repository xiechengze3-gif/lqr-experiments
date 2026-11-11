"""Prepare new namespaced delivery helpers from the reviewed X9 implementation."""
import ast
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    original=HERE.parent/'x9-20261106'
    transfers=(original/'transfer_report.py').read_text()
    replacements={
      "OUT = Path('/scratch/user/changze/lqr_experiments/results/x9-20261106')":"OUT = Path('/scratch/user/changze/lqr_experiments/results/x10-20261106/X10b')",
      "TMP = Path('/scratch/user/changze/lqr_experiments/tmp/x9-20261106')":"TMP = Path('/scratch/user/changze/lqr_experiments/tmp/x10-20261106')",
      "'x9-report-v1.tar.gz'":"'x10b-report-v1.tar.gz'",
      "OUT/'report-v1/verification.json'":"OUT/'report-v1/PRODUCTS_COMPLETE_v1.json'",
      "proof['status'] == 'COMPLETE' and coverage['paired_paths'] == 1024":"proof['status'] == 'MERGED_SAVED_STATISTICS_BASELINE_BYTES_PRESERVED' and coverage['paired_paths'] == 1280",
      'SEALED_X9_COMPLETE_DELIVERY':'SEALED_X10B_COMPLETE_DELIVERY',
      'VERIFIED_EXTRACTED_X9_DELIVERY':'VERIFIED_EXTRACTED_X10B_DELIVERY',
      'Seal and verify the X9 delivery':'Seal and verify the X10b delivery'}
    for before,after in replacements.items():
        assert before in transfers,before
        transfers=transfers.replace(before,after)
    provenance=(original/'copy_report_provenance.py').read_text()
    before="/scratch/user/changze/lqr_experiments/results/x9-20261106/report-v1"
    assert provenance.count(before)==1
    provenance=provenance.replace(before,'/scratch/user/changze/lqr_experiments/results/x10-20261106/X10b/report-v1')
    files={'transfer_actor_report.py':transfers,'copy_actor_provenance.py':provenance}
    proof={}
    for name,text in files.items():
        ast.parse(text,filename=name)
        with (HERE/name).open('x',encoding='utf-8',newline='\n') as stream:stream.write(text)
        proof[name]=hashlib.sha256((HERE/name).read_bytes()).hexdigest()
    with (HERE/'ACTOR_DELIVERY_SOURCE_PREPARATION_v1.json').open('x') as stream:
        json.dump(dict(status='NEW_IO_HELPERS_PREPARED',files=proof,
            original_transfer_sha256=hashlib.sha256((original/'transfer_report.py').read_bytes()).hexdigest(),
            changes='Only explicit output/archive namespaces, status labels and X10b coverage/product proof names/count.',
            numerical_work=0,new_jobs=0,SU=0),stream,indent=2)
    print(json.dumps(proof))


if __name__=='__main__':main()
