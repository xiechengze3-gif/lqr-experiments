"""Derive v6 controls without modifying the unused frozen home namespace."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

from prepare_scratch_pilot_v6 import ROOT


R = Path(__file__).resolve().parent
OLDROOT = '/home/changze/lqr-x12-flat-20261107-v5'


def read(n):
    return (R/n).read_text(encoding='utf-8')


def main(a):
    build = {
        'Deploy-ScratchStoragePilot-v6.ps1': read('Deploy-FlatStoragePilot-v5.ps1'),
        'Submit-ScratchStoragePilot-v6.ps1': read('Submit-FlatStoragePilot-v5.ps1'),
        'Receive-ScratchStoragePilot-v6.ps1': read('Receive-FlatStoragePilot-v5.ps1'),
        'verify_scratch_storage_pilot_v6.py': read('verify_flat_storage_pilot_v5.py'),
    }
    for n,text in list(build.items()):
        text = text.replace(OLDROOT,ROOT).replace('STORAGE_FLAT_MANIFEST_v5','STORAGE_SCRATCH_MANIFEST_v6')
        text = text.replace('STORAGE_FLAT_DEPLOYED_v5','STORAGE_SCRATCH_DEPLOYED_v6').replace('x12-storage-flat-v5.tar.gz','x12-storage-scratch-v6.tar.gz')
        text = text.replace('submit_flat_storage_pilot_v5.py','submit_scratch_storage_pilot_v6.py')
        text = text.replace('storage-flat-submission-v5','storage-scratch-submission-v6').replace('delivery-storage-flat-v5','delivery-storage-scratch-v6')
        text = text.replace('storage-io-v5','storage-io-v6').replace('STORAGE_FLAT_IO_VERIFIED_v5','STORAGE_SCRATCH_IO_VERIFIED_v6')
        text = text.replace('verify_flat_storage_pilot_v5.py','verify_scratch_storage_pilot_v6.py')
        text = text.replace('pilot_virtual_store_v5.py','pilot_virtual_store_v6.py')
        build[n] = text
    n = 'Deploy-ScratchStoragePilot-v6.ps1'
    text = build[n]
    text = text.replace("'31181','/home/changze'", "'231181','/scratch/user/changze'").replace('fs01-MDT0000','fs01-MDT0001')
    text = text.replace("assert int(m[7])-int(m[5])>=64", "assert int(m[7])-int(m[5])>=128\nassert check_output(['lfs','getdirstripe','-i',str(r.parent)],text=True).strip()=='1'")
    text = text.replace(".strip()=='0'", ".strip()=='1'").replace("r)=='0'", "r)=='1'")
    text = text.replace("r/'placement-probe.txt')=='0'", "r/'placement-probe.txt')=='1'").replace("r/n)=='0'", "r/n)=='1'")
    text = text.replace('not MDT0','not MDT1').replace('NEW_ROOT_AND_PROBE_MDT0','NEW_ROOT_AND_PROBE_MDT1')
    text = text.replace('directory_mdt=0,file_mdt=0','directory_mdt=1,file_mdt=1').replace('mdt=0,archive_sha256','mdt=1,archive_sha256')
    assert "=='0'" not in text and 'fs01-MDT0001' in text
    build[n] = text
    n = 'verify_scratch_storage_pilot_v6.py'
    build[n] = build[n].replace('pilot_limits(p)','pilot_limits(p, expected_mdt=1)')
    ast.parse(build[n], filename=n)
    assert all(OLDROOT not in t for t in build.values())
    hashes = {n:hashlib.sha256(t.encode()).hexdigest() for n,t in build.items()}
    if not a.validate_only:
        for n,t in build.items():
            with (R/n).open('x', encoding='utf-8', newline='\n') as f:
                f.write(t)
    print(json.dumps(dict(status='SCRATCH_PILOT_CONTROL_VALIDATION_PASS', validate_only=a.validate_only, hashes=hashes)))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--validate-only', action='store_true')
    main(p.parse_args())
