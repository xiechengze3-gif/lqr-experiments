"""Append the reviewed read-only query once; preserve the entire prior reply."""
import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
EXPECTED_REVIEW = '1a7847c226d6864a4fae78fd0212869577273e8a84726a362fdc08b44dab8de7'

def sha(data):
    return hashlib.sha256(data).hexdigest()

task = CHANNEL / 'CLAUDE_TASK.md'
assert sha(task.read_bytes()) == EXPECTED_REVIEW, 'Review changed: read it before delivery.'
reply = CHANNEL / 'CODEX_REPLY.md'
prior = reply.read_bytes()
assert b'## X8 QUERY' not in prior, 'Already delivered: do not append again.'
sources = json.loads((HERE / 'SOURCE_HASHES_v1.json').read_text())
for source in sources['source_hashes']:
    assert sha(Path(source['path']).read_bytes()) == source['sha256']
for source in sources['saved_median_source_hashes'].values():
    assert sha(Path(source['path']).read_bytes()) == source['sha256']
availability = json.loads((HERE / 'saved_median_availability_v1.json').read_text())
assert len(availability['rows']) == 128
draft = json.loads((HERE / 'X8_DRAFT_FEASIBILITY_v1.json').read_text())
assert draft['extrapolation']['total_draft_requested_SU'] == 12.6
manifest = {
    'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'authority_sha256': EXPECTED_REVIEW,
    'status': 'QUERY_ONLY_COMPLETE_NO_X8_GO',
    'additional_SU': 0,
    'files': [{'path': str(path.relative_to(HERE)), 'bytes': path.stat().st_size,
               'sha256': sha(path.read_bytes())}
              for path in sorted(HERE.iterdir()) if path.is_file()],
    'checks': {'saved_median_queries': 128, 'existing_source_hashes_unchanged': True,
               'new_jobs': 0, 'new_transitions': 0, 'new_controller_evaluations': 0,
               'new_interpolations': 0, 'moved_files': 0, 'deleted_files': 0},
}
manifest_path = HERE / 'QUERY_MANIFEST_v1.json'
with manifest_path.open('x', encoding='utf-8') as stream:
    json.dump(manifest, stream, indent=2)
details = (HERE / 'QUERY_DETAILS.md').read_text(encoding='utf-8')
body = details.split('\n', 1)[1].lstrip().replace('\n## ', '\n### ')
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
section = ('\n\n## X8 QUERY\n\nDelivered ' + stamp + '. X7 REPORT ACCEPTED is acknowledged.\n\n'
           + body.rstrip() + '\n\nDelivery: `experiments/x8-query-20261105/QUERY_DETAILS.md`; '
           'all metadata, saved-median censoring rows, cost formula and retention exclusions are '
           'bound by `QUERY_MANIFEST_v1.json`, SHA256 `' + sha(manifest_path.read_bytes())
           + '`. Read-only source/hash/bracket checks passed; additional spend **0 SU**, '
           'no new job.\n\nSTATUS: QUERY DONE X8\n')
encoded = section.encode('utf-8')
with reply.open('ab') as stream:
    stream.write(encoded)
after = reply.read_bytes()
assert after == prior + encoded, 'Append-only preservation failed.'
assert after.rstrip().endswith(b'STATUS: QUERY DONE X8')
receipt = {'status': 'APPEND_ONLY_QUERY_DELIVERED', 'delivered_utc': stamp,
           'review_sha256': EXPECTED_REVIEW, 'prior_reply_bytes': len(prior),
           'prior_reply_sha256': sha(prior), 'appended_bytes': len(encoded),
           'appended_sha256': sha(encoded), 'current_reply_sha256': sha(after),
           'manifest_sha256': sha(manifest_path.read_bytes()),
           'prior_reply_preserved_exactly': True, 'new_jobs': 0, 'additional_SU': 0}
with (HERE / 'APPEND_RECEIPT_v1.json').open('x', encoding='utf-8') as stream:
    json.dump(receipt, stream, indent=2)
print(json.dumps(receipt))
