"""Verify and safely extract the result archive; performs no numerical analysis."""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path


def main(archive, destination, expected_sha256):
    archive, destination = Path(archive), Path(destination)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise RuntimeError('Archive SHA256 mismatch')
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        for member in members:
            target = (root / member.name).resolve()
            if not target.is_relative_to(root) or member.issym() or member.islnk():
                raise RuntimeError(f'Unsafe archive member: {member.name}')
            if not member.isfile() and not member.isdir():
                raise RuntimeError(f'Unsupported archive member: {member.name}')
        tar.extractall(root, members=members, filter='data')
    files = sorted(path for path in root.rglob('*') if path.is_file())
    inventory = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in files if path.name != 'LOCAL_ARTIFACT_SHA256.json'}
    (root / 'LOCAL_ARTIFACT_SHA256.json').write_text(json.dumps(inventory, indent=2) + '\n')
    print(json.dumps(dict(archive=str(archive), archive_sha256=digest, extracted_files=len(inventory), destination=str(root))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    main(args.archive, args.destination, args.sha256)
