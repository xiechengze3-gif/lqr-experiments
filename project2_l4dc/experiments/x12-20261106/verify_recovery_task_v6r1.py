"""Verify one completed recovery archive and append journal on E."""
import argparse
import json
import re
from pathlib import Path

from virtual_task_store_v2 import file_sha, verify_archive


def main(a):
    m=re.fullmatch(r'(n60-nine-(NPG|PI))-task-(0[0-9]|[12][0-9]|3[01])',a.key)
    assert m is not None and re.fullmatch(r'\d+_\d+',a.job)
    folder=Path(__file__).resolve().parent/'delivery-recovery-tasks-v6r1'
    archive=folder/(a.key+'.tar')
    journal=folder/(a.key+'.jsonl')
    p=json.loads(journal.read_bytes().splitlines()[-1])
    assert p['status']=='COMPLETE' and p['kind']=='TASK_FINAL' and p['config_sha256']==a.config
    assert (p['group'],p['index'])==(m[1],int(m[3]))
    assert p['index']==int(a.job.split('_')[1])
    assert len(p['paths'])==9
    assert p['archive_bytes']==archive.stat().st_size and p['archive_sha256']==file_sha(archive)
    count=verify_archive(archive,p['members'])
    receipt=dict(status='TASK_ARCHIVE_AND_MEMBERS_VERIFIED_ON_E',key=a.key,job=a.job,
                 archive_sha256=p['archive_sha256'],journal_sha256=file_sha(journal),members=count,
                 accepted_transitions=p['accepted_transitions'],config_sha256=a.config,paths=p['paths'])
    with (folder/(a.key+'.verified.json')).open('x',encoding='utf-8') as f:
        json.dump(receipt,f,indent=2)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--key',required=True);p.add_argument('--job',required=True);p.add_argument('--config',required=True);main(p.parse_args())
