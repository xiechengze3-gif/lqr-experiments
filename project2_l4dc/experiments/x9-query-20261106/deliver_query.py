"""Deliver one metadata-only X9 query; preserve the existing channel reply."""
import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
OLD = HERE.parent / 'x6-20261101/X6b-protocol-v2'
EXPECTED_REVIEW = '13f2bc95e06b5358f0f67aa08e3ca5c54d91bd23c16e9ffab7d0460fe767ea1a'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


task = CHANNEL / 'CLAUDE_TASK.md'
review = task.read_bytes()
assert sha(review) == EXPECTED_REVIEW, 'Review changed: reread before delivery.'
assert b'## X9 QUERY (22:10 CDT 11/05)' in review
reply = CHANNEL / 'CODEX_REPLY.md'
prior = reply.read_bytes()
assert b'## X9 QUERY' not in prior, 'Already delivered; do not append again.'
for name in ['SOURCE_HASHES_v1.json', 'QUERY_MANIFEST_v1.json', 'APPEND_RECEIPT_v1.json']:
    assert not (HERE / name).exists(), 'Partial receipt exists; inspect before proceeding.'

identity = json.loads((HERE / 'x6b_reuse_identity_v1.json').read_text(encoding='utf-8'))
assert identity['status'] == 'SAVED_METADATA_IDENTITY_PASS_NO_MODEL_EXECUTION'
assert len(identity['models']) == 8 and len(identity['paired_paths']) == 256
assert len(identity['sources']) == 5
refs = [identity['config']] + identity['sources'] + identity['models'] + identity['paired_paths']
for ref in refs:
    assert sha(Path(ref['path']).read_bytes()) == ref['sha256'], ref['path']
draft = json.loads((HERE / 'DRAFT_FEASIBILITY_v1.json').read_text(encoding='utf-8'))
assert draft['primitive_transitions_new'] == 128849584128
assert draft['paired_paths_new'] == 1024 and draft['arm_paths_new'] == 2048
assert abs(draft['formal_requested_SU_new'] - 46.93333333333333) < 1e-10
assert abs(draft['total_requested_SU_proposal'] - 49.93333333333333) < 1e-10
assert draft['additional_SU_this_query'] == 0
assert draft['recommended_same_cost_grid'] == [0, .05, .1, .2, .4]

extra_paths = [OLD / 'formal-plan.json', OLD / 'measured-costs.csv',
               OLD.parent / 'X6b-report-v1/summary.csv',
               OLD.parent / 'estimation.py',
               Path('C:/Users/24375/Projects/project2_l4dc/sections/04-upper.tex')]
extra_refs = [{'path': str(p.resolve()), 'bytes': p.stat().st_size,
               'sha256': sha(p.read_bytes())} for p in extra_paths]
assert extra_refs[0]['sha256'] == draft['source_plan']['sha256']
source_proof = {'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'review_sha256': EXPECTED_REVIEW,
                'verified_existing_references': refs,
                'additional_existing_sources': extra_refs,
                'new_simulations': 0, 'new_controller_evaluations': 0}
write_new(HERE / 'SOURCE_HASHES_v1.json', source_proof)

manifest = {
    'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'authority_sha256': EXPECTED_REVIEW,
    'status': 'X9_QUERY_COMPLETE_NO_GO_NO_NEW_COMPUTE',
    'files': [{'path': str(p.relative_to(HERE)), 'bytes': p.stat().st_size,
               'sha256': sha(p.read_bytes())}
              for p in sorted(HERE.iterdir()) if p.is_file()],
    'checks': {'scientific_source_hashes_verified': 5, 'saved_model_hashes_verified': 8,
               'saved_paired_path_receipts_verified': 256,
               'existing_sources_unchanged': True, 'new_jobs': 0,
               'new_primitive_transitions': 0, 'new_model_solves': 0,
               'new_estimator_fits': 0, 'moved_files': 0, 'deleted_files': 0,
               'additional_SU': 0},
}
manifest_path = HERE / 'QUERY_MANIFEST_v1.json'
write_new(manifest_path, manifest)
details = (HERE / 'QUERY_DETAILS.md').read_text(encoding='utf-8')
body = details.split('\n', 1)[1].lstrip().replace('\n## ', '\n### ')
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
section = ('\n\n## X9 QUERY\n\nDelivered ' + stamp + '. No X9 GO is inferred.\n\n'
           + body.rstrip() + '\n\nDelivery: `experiments/x9-query-20261106/QUERY_DETAILS.md`; '
           'source/model/receipt identity, saved timings and draft costs are bound by '
           '`QUERY_MANIFEST_v1.json`, SHA256 `' + sha(manifest_path.read_bytes())
           + '`. Saved-source verification passed. Additional spend **0 SU**; **0 new jobs**.\n\n'
           'STATUS: QUERY DONE X9\n')
encoded = section.encode('utf-8')
# Recheck the live review immediately before the single append.
assert sha(task.read_bytes()) == EXPECTED_REVIEW, 'Review changed during preparation.'
assert reply.read_bytes() == prior, 'Reply changed concurrently; inspect before appending.'
with reply.open('ab') as stream:
    stream.write(encoded)
after = reply.read_bytes()
assert after == prior + encoded, 'Append-only preservation failed.'
assert after.rstrip().endswith(b'STATUS: QUERY DONE X9')
receipt = {'status': 'APPEND_ONLY_X9_QUERY_DELIVERED', 'delivered_utc': stamp,
           'review_sha256': EXPECTED_REVIEW, 'prior_reply_bytes': len(prior),
           'prior_reply_sha256': sha(prior), 'appended_bytes': len(encoded),
           'appended_sha256': sha(encoded), 'current_reply_sha256': sha(after),
           'manifest_sha256': sha(manifest_path.read_bytes()),
           'prior_reply_preserved_exactly': True, 'new_jobs': 0, 'additional_SU': 0}
write_new(HERE / 'APPEND_RECEIPT_v1.json', receipt)
print(json.dumps(receipt))
