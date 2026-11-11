"""Include both rejected corrections and successful v3 metadata in X12 backups."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent;D=R/'runtime-prepared-v1'
old=(D/'raw_delivery_v1.py').read_text()
a="[OUT/'calibration-v1', eq, OUT/'failures', OUT/'submission-correction-v2']"
b="[OUT/'calibration-v1', eq, OUT/'failures', OUT/'submission-correction-v2', OUT/'submission-correction-v3']"
assert old.count(a)==1;s=old.replace(a,b)
assert s.count('numerical_reanalysis=False')==1
p=D/'raw_delivery_v2.py'
with p.open('xb') as f:f.write(s.encode())
with (D/'RAW_TRANSFER_SOURCE_PROOF_v2.json').open('x') as f:json.dump(dict(source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
    old_source_sha256=hashlib.sha256((D/'raw_delivery_v1.py').read_bytes()).hexdigest(),only_change='include v3 corrected submission receipts; retain both rejected attempts',
    unpack_unchanged=True,new_training_transitions=0,prepared_not_uploaded=True),f,indent=2)
print(json.dumps(dict(status='RAW_V2_PREPARED_NOT_UPLOADED',sha256=hashlib.sha256(p.read_bytes()).hexdigest())))
