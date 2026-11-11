"""Stdlib-only safe extraction/hash check of the new pilot metadata/model delivery."""
import hashlib
import json
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOWNLOAD = HERE/'pilot-download-v1'
archive = DOWNLOAD/'pilot-metadata-v1.tar.gz'
manifest_path = DOWNLOAD/'pilot-metadata-v1.tar.json'
proof = json.loads(manifest_path.read_text())
assert hashlib.sha256(archive.read_bytes()).hexdigest() == proof['archive_sha256']
expected = {r['path']: r for r in proof['files']}
assert len(expected) == 70
out = HERE/'pilot-delivery-v1'
assert not out.exists(), 'Never merge into an existing delivery.'
with tarfile.open(archive, 'r:gz') as tf:
    members = tf.getmembers()
    assert len(members) == 70 and {m.name for m in members} == set(expected)
    for member in members:
        assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
        payload = tf.extractfile(member).read()
        assert len(payload) == expected[member.name]['bytes']
        assert hashlib.sha256(payload).hexdigest() == expected[member.name]['sha256']
    out.mkdir()
    for member in members:
        target = out/member.name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(tf.extractfile(member).read())
receipt = dict(status='VERIFIED_METADATA_AND_MODEL_BYTES_NO_ARRAY_LOADING', files=70,
               archive_sha256=proof['archive_sha256'], new_scientific_execution=False)
with (HERE/'PILOT_DELIVERY_VERIFIED_v1.json').open('x') as stream:
    json.dump(receipt, stream, indent=2)
print(json.dumps(receipt))
