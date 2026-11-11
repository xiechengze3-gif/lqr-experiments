"""Append measured X10b pilot/resource plan once, before formal submission."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--expected-review-sha256', required=True)
    args = p.parse_args()
    review = (CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert sha(review) == args.expected_review_sha256
    receipt = HERE/'ACTOR_PILOT_DONE_APPEND_RECEIPT_v1.json'
    assert not receipt.exists()
    manifest = json.loads((HERE/'ACTOR_FORMAL_MANIFEST_v1.json').read_text())
    plan = manifest['plan']
    assert plan['status'] == 'ALL_GATES_PASS_READY_TO_FREEZE' and all(plan['checks'].values())
    audit = json.loads((HERE/'prepared-actor-formal-v1/PILOT_AUDIT_v1.json').read_text())
    prior = (CHANNEL/'CODEX_REPLY.md').read_bytes()
    assert b'## X10b PILOT\n' not in prior
    lines = ['\n\n## X10b PILOT\n',
             'All fixed saved-record/array/RNG/count/source/RSS/Slurm checks PASS. The single old path was replayed only as the explicitly authorized validation check; no performance readout, retuning or new scientific replication. Every replay/timing transition retained.\n',
             '|role|body seconds|process seconds|peak RSS MiB|physical transitions|',
             '|---|---:|---:|---:|---:|']
    for role in ['equivalence', 'NPG', 'PI']:
        r = audit['pilot_roles'][role]['receipt']
        lines.append('|%s|%s|%.6f|%.3f|%d|' % (role, r.get('body_seconds', 'N/A'),
                     r['seconds'], r['peak_RSS_KiB']/1024, r['primitive_transitions']))
    lines += ['\n|formal group|predicted body s|guarded wall min|requested SU|',
              '|---|---:|---:|---:|']
    for group in plan['groups']:
        lines.append('|%s|%.6f|%d|%.6f|' % (group['id'], group['body_seconds'], group['wall_minutes'], group['requested_bound_SU']))
    lines += [('\nCompleted pilot Slurm elapsed %.6f SU; pilot requested upper %.6f SU. Formal actual-spend forecast %.6f SU; formal requested upper %.6f SU. With 8 SU report reserve: **actual forecast %.6f /160 SU; requested upper %.6f /200 SU**. These are overlapping elapsed/requested categories, not additive consumed charges; AMS settlement is separate.' %
              (plan['completed_pilot_Slurm_elapsed_SU'], plan['pilot_requested_upper_SU'],
               plan['formal_predicted_actual_SU'], plan['formal_requested_upper_SU'],
               plan['cumulative_predicted_actual_SU'], plan['cumulative_requested_upper_SU'])),
              ('\nAll X9 compute including REPORT is COMPLETED. Formal uses 8 serial arrays of 32 tasks, each maximum 8 concurrent, order n72/n48/n36/n24 each NPG then PI. Conditional completion %s with frozen wall guards, 3.5 h report critical path and 6 h queue allowance; target %s. Queue delays remain uncertain.' % (plan['conditional_finish_utc'], plan['deadline_utc'])),
              ('\nFrozen formal config SHA256 `%s`; manifest `experiments/x10-20261106/ACTOR_FORMAL_MANIFEST_v1.json`; all seven science files and 32 model bytes preserved. Under X10 DECISIONS, all gates PASS; proceeding to FORMAL automatically. No automatic retries or paper edits.' % manifest['config_sha256']),
              '\nSTATUS: PILOT DONE X10b\n']
    section = ('\n'.join(lines)).encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes() == review
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes() == prior
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:
        stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes() == prior+section
    with receipt.open('x') as stream:
        json.dump(dict(prior_bytes=len(prior), appended_bytes=len(section), prior_preserved=True,
                       review_sha256=sha(review), formal_config_sha256=manifest['config_sha256']), stream, indent=2)
    print(json.dumps(dict(status='PILOT_DONE_APPENDED', experiment='X10b')))


if __name__ == '__main__':
    main()
