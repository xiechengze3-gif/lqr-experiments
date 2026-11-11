"""Match local manifest to Grace files, then build and verify a complete snapshot."""
import argparse
import collections
import hashlib
import json
import os
import re
import stat
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path("/scratch/user/changze/lqr_experiments")


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2), encoding="utf-8")
    tmp.replace(path)


def match_cached(run):
    """Use positively hashed files; final snapshot verification checks them again."""
    manifest = json.loads((run / "manifest.json").read_text())
    cache = {}
    for filename in ("hash-cache.json", "hash-cache-fast.json"):
        if (run / filename).exists():
            cache.update(json.loads((run / filename).read_text()))
    lookup = {(Path(path).name, saved[0], saved[2]): path for path, saved in cache.items()}
    matches, missing = {}, []
    missing_bytes = 0
    for record in manifest["files"]:
        key = (Path(record["id"]).name, record["size"], record["sha256"])
        if key in lookup:
            matches[record["id"]] = lookup[key]
        else:
            missing.append(record["id"])
            missing_bytes += record["size"]
    result = {"status": "MATCHED", "manifest_sha256": digest(run / "manifest.json"),
              "matches": matches, "missing": missing, "matched_files": len(matches),
              "missing_files": len(missing), "missing_bytes": missing_bytes}
    save(run / "remote-match.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("matches", "missing")}), flush=True)


def prehash_fast(run):
    manifest = json.loads((run / "manifest.json").read_text())
    wanted = collections.defaultdict(set)
    for r in manifest["files"]:
        wanted[(Path(r["id"]).name, r["size"])].add(r["sha256"])
    names = {key[0] for key in wanted}
    result_names = {r["id"].split("/")[1] for r in manifest["files"] if r["id"].startswith("results/")}
    ids = set(re.findall(r"[0-9a-f]{16}", " ".join(result_names)))
    aliases = {name.removeprefix("grace-").replace("-complete-", "-").replace("-smoke-", "-") for name in result_names}
    roots = [BASE / name for name in ("archives", "releases", "packages", "uploads", "incoming", "accounting")]
    candidates = [p for p in BASE.iterdir() if p.name in names]
    for entry in (BASE / "results").iterdir():
        if entry.name in names and entry.is_file():
            candidates.append(entry)
        if entry.name in result_names or entry.name in aliases or any(key in entry.name for key in ids):
            if entry.is_dir() and not entry.is_symlink():
                roots.append(entry)
    for root in roots:
        for base, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()]
            candidates.extend(Path(base) / name for name in files if name in names)
    found = collections.defaultdict(set)
    def check(path):
        before = path.stat(follow_symlinks=False)
        key = (path.name, before.st_size)
        if not stat.S_ISREG(before.st_mode) or key not in wanted or wanted[key].issubset(found[key]):
            return None
        sha = digest(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError("File changed during hashing: " + str(path))
        found[key].add(sha)
        return str(path), [after.st_size, after.st_mtime_ns, sha]
    cache = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(check, path) for path in candidates]
        for i, future in enumerate(as_completed(futures)):
            checked = future.result()
            if checked is not None:
                cache[checked[0]] = checked[1]
            if (i + 1) % 2000 == 0:
                save(run / "hash-cache-fast.json", cache)
                print(json.dumps({"checked_paths": i + 1, "of": len(candidates), "hashed_paths": len(cache)}), flush=True)
    save(run / "hash-cache-fast.json", cache)
    print(json.dumps({"status": "PREHASHED", "cached_paths": len(cache)}), flush=True)


def match(run, prehash=False):
    manifest = json.loads((run / ("inventory.json" if prehash else "manifest.json")).read_text())
    cache_path = run / "hash-cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    wanted = collections.defaultdict(set)
    for r in manifest["files"]:
        key = (Path(r["id"]).name, r["size"])
        wanted[key]
        if not prehash:
            wanted[key].add(r["sha256"])
    wanted_names = {key[0] for key in wanted}
    result_names = {r["id"].split("/")[1] for r in manifest["files"] if r["id"].startswith("results/")}
    result_ids = set(re.findall(r"[0-9a-f]{16}", " ".join(result_names)))
    aliases = {name.removeprefix("grace-").replace("-complete-", "-").replace("-smoke-", "-") for name in result_names}
    index = collections.defaultdict(list)
    scanned = 0
    for path in BASE.iterdir():
        if path.is_file() and not path.is_symlink():
            key = (path.name, path.stat().st_size)
            if key in wanted:
                index[key].append(path)
    roots = [BASE / name for name in ("archives", "releases", "packages", "uploads", "incoming", "accounting")]
    for entry in (BASE / "results").iterdir():
        if entry.name in wanted_names and entry.is_file() and not entry.is_symlink():
            key = (entry.name, entry.stat().st_size)
            if key in wanted:
                index[key].append(entry)
        if entry.name in result_names or entry.name in aliases or any(key in entry.name for key in result_ids):
            if entry.is_dir() and not entry.is_symlink():
                roots.append(entry)
    for root in roots:
        print(json.dumps({"scan_root": str(root)}), flush=True)
        for base, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()]
            for filename in files:
                scanned += 1
                if filename not in wanted_names:
                    continue
                path = Path(base) / filename
                try:
                    state = path.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if not stat.S_ISREG(state.st_mode):
                    continue
                size = state.st_size
                key = (filename, size)
                if key in wanted:
                    index[key].append(path)
            if scanned % 10000 < len(files):
                print(json.dumps({"scanned": scanned, "candidate_keys": len(index)}), flush=True)
    def check(item):
        key, paths = item
        found = {}
        for path in paths:
            state = path.stat()
            saved = cache.get(str(path))
            if saved and [state.st_size, state.st_mtime_ns] == saved[:2]:
                sha = saved[2]
            else:
                sha = digest(path)
                after = path.stat()
                if (state.st_size, state.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise RuntimeError("Remote file changed while hashing: " + str(path))
                cache[str(path)] = [state.st_size, state.st_mtime_ns, sha]
            if sha in wanted[key]:
                found[sha] = str(path)
            if prehash or set(found) == wanted[key]:
                break
        return key, found
    lookup = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(check, item) for item in index.items()]
        for i, future in enumerate(as_completed(futures)):
            key, found = future.result()
            for sha, path in found.items():
                lookup[(key[0], key[1], sha)] = path
            if i % 2000 == 0:
                print(json.dumps({"hashed_keys": i + 1, "of": len(index)}), flush=True)
    save(cache_path, cache)
    if prehash:
        print(json.dumps({"status": "PREHASHED", "cached_paths": len(cache)}), flush=True)
        return
    matches, missing = {}, []
    for r in manifest["files"]:
        key = (Path(r["id"]).name, r["size"], r["sha256"])
        if key in lookup:
            matches[r["id"]] = lookup[key]
        else:
            missing.append(r["id"])
    result = {"status": "MATCHED", "manifest_sha256": digest(run / "manifest.json"),
              "matches": matches, "missing": missing, "matched_files": len(matches),
              "missing_files": len(missing),
              "missing_bytes": sum(r["size"] for r in manifest["files"] if r["id"] in set(missing))}
    save(run / "remote-match.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("matches", "missing")}), flush=True)


def finalize(run):
    manifest = json.loads((run / "manifest.json").read_text())
    matches = json.loads((run / "remote-match.json").read_text())
    upload = json.loads((run / "upload.json").read_text())
    assert digest(run / "manifest.json") == matches["manifest_sha256"]
    assert digest(run / "missing.tar.gz") == upload["sha256"]
    snapshot = run / "snapshot"
    if snapshot.exists():
        raise RuntimeError("Snapshot already exists; inspect it before rerunning finalize")
    snapshot.mkdir()
    directories = set()
    for record in manifest["files"]:
        relative = Path(record["id"])
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("Unsafe manifest path")
        directories.add((snapshot / relative).parent)
    for directory in sorted(directories, key=lambda path: len(path.parts)):
        directory.mkdir(parents=True, exist_ok=True)
    missing = set(matches["missing"])
    with tarfile.open(run / "missing.tar.gz", "r:gz") as archive:
        members = archive.getmembers()
        if {m.name for m in members} != missing or len(members) != len(missing):
            raise RuntimeError("Unexpected archive coverage")
        for member in members:
            if not member.isfile() or member.name.startswith("/") or ".." in Path(member.name).parts:
                raise RuntimeError("Unsafe archive member")
            target = snapshot / member.name
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with archive.extractfile(member) as src, os.fdopen(descriptor, "wb") as dst:
                for block in iter(lambda: src.read(8 * 1024 * 1024), b""):
                    dst.write(block)
    def link(item):
        file_id, source = item
        target = snapshot / file_id
        os.link(source, target)  # Frozen existing results retain an independent directory entry.
    with ThreadPoolExecutor(max_workers=8) as pool:
        for _ in pool.map(link, matches["matches"].items()):
            pass
    def check(record):
        target = snapshot / record["id"]
        if target.stat().st_size != record["size"] or digest(target) != record["sha256"]:
            raise RuntimeError("Snapshot mismatch: " + record["id"])
        return record["size"]
    total = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, size in enumerate(pool.map(check, manifest["files"])):
            total += size
            if i % 3000 == 0:
                print(json.dumps({"verified": i + 1, "of": len(manifest["files"])}), flush=True)
    result = {"status": "PASS", "manifest_sha256": digest(run / "manifest.json"),
              "verified_files": len(manifest["files"]), "verified_bytes": total,
              "snapshot": str(snapshot), "existing_hardlinks": len(matches["matches"]),
              "uploaded_files": len(missing), "verified_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    save(run / "remote-verified.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prehash", "prehash-fast", "match", "match-cached", "finalize"])
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prehash":
        match(args.run, prehash=True)
    elif args.action == "prehash-fast":
        prehash_fast(args.run)
    elif args.action == "match-cached":
        match_cached(args.run)
    elif args.action == "match":
        match(args.run)
    else:
        finalize(args.run)
