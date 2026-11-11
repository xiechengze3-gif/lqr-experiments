"""Append per-array FORMAL progress; never declares stage DONE or submits work."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--progress',type=Path,required=True)
    p.add_argument('--accounting',type=Path,required=True);p.add_argument('--review-sha256',required=True)
    a=p.parse_args();channel=ROOT.parents[2];task=channel/'CLAUDE_TASK.md'
    assert sha(task)==a.review_sha256
    d=json.loads(a.progress.read_text());b=json.loads(a.accounting.read_text())
    assert d['full_tasks']==384 and b['cap_requested_SU']==400
    config=json.loads((ROOT/'prepared-formal-v1/formal-config.json').read_text())
    assert all(sha(ROOT/name)==digest for name,digest in config['scientific_sources'].items())
    table=[]
    for group in d['groups']:
        s=group['states'];other=sum(v for k,v in s.items() if k not in ['COMPLETED','RUNNING','PENDING'])
        table.append(f"|{group['group']}|{group['job']}|{s.get('COMPLETED',0)}/32|{s.get('RUNNING',0)}|{s.get('PENDING',0)}|{other}|{group['completed_checkpoints']}/{group['expected_checkpoints']}|")
    relative=lambda path:path.resolve().relative_to(channel).as_posix()
    errors=('No infrastructure/Slurm failure or HARD_FAILURE records.' if not d['errors'] else
            '**FAILURE REVIEW REQUIRED; no retry or resubmission has been performed.**\n\n'+
            '```json\n'+json.dumps(d['errors'],indent=2)+'\n```')
    body=f'''

## X6b FORMAL

Progress at{d['checked_utc']}: **{d['completed_tasks']}/384** Slurm tasks
completed;{d['done_files']} DONE files. {errors}

|group|array job|completed|running|pending|other state|complete-stage checkpoints|
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(table)}

Exact local snapshots:`{relative(a.progress)}` and `{relative(a.accounting)}`.
No outcome-based retuning, scope change, cancellation or retry. Accepted science
source/config hashes remain unchanged; no old result/release or paper TeX edited.
Conditional frozen REPORT begins only after all12 arrays complete and coverage
counts are audited; experiment FORMAL is not yet declared DONE.

X6 cumulative requested{b['cumulative_requested_SU']:.9f}/400SU; report reserve6.5SU.
Slurm elapsed{b['slurm_elapsed_billing_SU']:.9f}SU; AMS settled
{b['ams_settled_walltime_slots_SU']:.9f}SU at{b['checked_utc']}
(overlapping views,never add). Review reread
{datetime.datetime.now(datetime.timezone.utc).isoformat()},task SHA `{a.review_sha256}`.

STATUS: FORMAL RUNNING X6b
'''
    assert sha(task)==a.review_sha256
    with (channel/'CODEX_REPLY.md').open('a',encoding='utf-8',newline='') as stream:stream.write(body)
    print(json.dumps(dict(status='PROGRESS_APPENDED',completed=d['completed_tasks'],
                         errors=len(d['errors']),stage_done=False)))


if __name__=='__main__':main()
