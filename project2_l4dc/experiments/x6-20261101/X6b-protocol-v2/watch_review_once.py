"""One read-only review snapshot; no resident host,compute or result mutation."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--expected-sha256',required=True)
    args=parser.parse_args()
    channel=Path(__file__).resolve().parents[3]
    task=channel/'CLAUDE_TASK.md'
    payload=task.read_bytes()
    digest=hashlib.sha256(payload).hexdigest()
    changed=digest.lower()!=args.expected_sha256.lower()
    result=dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        status='REVIEW_CHANGED' if changed else 'REVIEW_UNCHANGED',
        task_sha256=digest,read_only=True)
    if changed:result['review_tail']='\n'.join(payload.decode('utf-8-sig').splitlines()[-180:])
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
