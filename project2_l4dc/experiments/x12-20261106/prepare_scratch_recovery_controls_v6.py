"""Select the verified scratch location in the prepared recovery controls."""
import argparse
import hashlib
import json
from pathlib import Path

from prepare_scratch_pilot_v6 import ROOT


def main(validate_only):
    r=Path(__file__).resolve().parent
    files={}
    for old,new in [('Deploy-RecoveryRelease-v5.ps1','Deploy-RecoveryRelease-v6.ps1'),
                    ('Invoke-RecoveryStage-v5.ps1','Invoke-RecoveryStage-v6.ps1')]:
        source=(r/old).read_text(encoding='utf-8')
        text=source.replace('/home/changze/lqr-x12-flat-20261107-v5', ROOT)
        text=text.replace('STORAGE_FLAT_IO_VERIFIED_v5','STORAGE_SCRATCH_IO_VERIFIED_v6')
        text=text.replace('recovery-release-v5','recovery-release-v6').replace('RECOVERY_RELEASE_DEPLOYED_v5','RECOVERY_RELEASE_DEPLOYED_v6')
        text=text.replace('.strip()==\'0\'', '.strip()==\'1\'').replace('hashes=actual,mdt=0','hashes=actual,mdt=1')
        text=text.replace('recovery-$Stage-receipt-v5','recovery-$Stage-receipt-v6').replace('recovery-preflight-receipt-v5','recovery-preflight-receipt-v6')
        assert ROOT in text and 'lqr-x12-flat-20261107-v5' not in text and text != source
        files[new]=text
    if not validate_only:
        for n,t in files.items():
            with (r/n).open('x',encoding='utf-8',newline='\n') as f:
                f.write(t)
    print(json.dumps(dict(status='SCRATCH_RECOVERY_CONTROL_PREPARED', validate_only=validate_only,
                          files={n:hashlib.sha256(t.encode()).hexdigest() for n,t in files.items()})))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--validate-only',action='store_true');main(p.parse_args().validate_only)
