"""Content-verified LQR local-to-Grace migration; no numerical experiments."""
import argparse
import collections
import hashlib
import io
import json
import os
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT = Path(r"E:\ChatGPT\Projects\LQR_experiments")
ROOTS = {
    "results": Path(r"E:\ChatGPT\Results\LQR_experiments"),
    "data": Path(r"E:\ChatGPT\Data\LQR_experiments"),
    "project": PROJECT,
    "cache": Path(r"E:\ChatGPT\Cache\LQR_experiments"),
    "temp": Path(r"E:\ChatGPT\Temp\LQR_experiments"),
    "rescued": Path(r"E:\ChatGPT\Results\storage-cleanup-20261025\preserved-archive-files"),
}


def save(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inventory(run):
    files = []
    for label, root in ROOTS.items():
        if not root.exists():
            continue
        for base, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if d != ".git" and not (Path(base) / d).is_symlink()
                       and (Path(base) / d).resolve() != run.resolve()]
            for name in names:
                path = Path(base) / name
                try:
                    files.append({"id": label + "/" + path.relative_to(root).as_posix(), "size": path.stat().st_size})
                except FileNotFoundError:
                    pass
    save(run / "inventory.json", {"files": files})
    print(json.dumps({"inventory_files": len(files)}), flush=True)


def manifest(run):
    records, vanished = [], []
    started = time.time()
    cached = {}
    proof_path = Path(r"E:\ChatGPT\Results\storage-cleanup-20261025\verified-archives.json")
    if proof_path.exists():
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        if Path(proof["root"]) != ROOTS["results"]:
            proof = {"records": []}
        for archive in proof["records"]:
            if archive["status"] == "verified_redundant":
                for saved in archive["retained_files"]:
                    cached[(saved["path"], saved["bytes"], saved["mtime_ns"])] = saved["sha256"]
    reused = 0
    for label, root in ROOTS.items():
        if not root.exists():
            continue
        for base, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if d != ".git" and not (Path(base) / d).is_symlink()
                       and (Path(base) / d).resolve() != run.resolve()]
            for name in sorted(names):
                path = Path(base) / name
                if path.is_symlink():
                    raise RuntimeError(f"Unexpected symlink: {path}")
                try:
                    before = path.stat()
                    sha = cached.get((str(path), before.st_size, before.st_mtime_ns))
                    if sha is None:
                        sha = digest(path)
                    else:
                        reused += 1
                    after = path.stat()
                except FileNotFoundError:
                    vanished.append(str(path))
                    continue
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise RuntimeError(f"File changed while hashing: {path}")
                records.append({"id": label + "/" + path.relative_to(root).as_posix(),
                                "local": str(path), "size": after.st_size,
                                "mtime_ns": after.st_mtime_ns, "sha256": sha})
                if len(records) % 2000 == 0:
                    save(run / "manifest-progress.json", {"files": records, "vanished": vanished})
                    print(json.dumps({"hashed": len(records), "bytes": sum(r["size"] for r in records),
                                      "reused_prior_verified_hashes": reused,
                                      "elapsed_s": round(time.time() - started)}), flush=True)
    value = {"version": 1, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "roots": {k: str(v) for k, v in ROOTS.items()}, "files": records,
             "vanished_during_inventory": vanished, "total_bytes": sum(r["size"] for r in records)}
    save(run / "manifest.json", value)
    print(json.dumps({"status": "manifest_complete", "files": len(records),
                      "bytes": value["total_bytes"], "vanished": len(vanished)}), flush=True)


def manifest_fast(run):
    cached = {}
    checkpoint = run / "manifest-progress.json"
    if checkpoint.exists():
        for r in json.loads(checkpoint.read_text(encoding="utf-8"))["files"]:
            cached[(r["local"], r["size"], r["mtime_ns"])] = r["sha256"]
    proof_path = Path(r"E:\ChatGPT\Results\storage-cleanup-20261025\verified-archives.json")
    if proof_path.exists():
        proof = json.loads(proof_path.read_text())
        if Path(proof["root"]) == ROOTS["results"]:
            for archive in proof["records"]:
                if archive["status"] == "verified_redundant":
                    for r in archive["retained_files"]:
                        cached[(r["path"], r["bytes"], r["mtime_ns"])] = r["sha256"]
    paths = []
    for label, root in ROOTS.items():
        if not root.exists():
            continue
        for base, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if d != ".git" and not (Path(base) / d).is_symlink()
                       and (Path(base) / d).resolve() != run.resolve()]
            paths.extend((label, root, Path(base) / name) for name in names)
    def check(item):
        label, root, path = item
        if path.is_symlink():
            raise RuntimeError(f"Unexpected symlink: {path}")
        before = path.stat()
        sha = cached.get((str(path), before.st_size, before.st_mtime_ns))
        reused = sha is not None
        if sha is None:
            sha = digest(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f"Changed during hashing: {path}")
        return {"id": label + "/" + path.relative_to(root).as_posix(), "local": str(path),
                "size": after.st_size, "mtime_ns": after.st_mtime_ns, "sha256": sha}, reused
    records, reused = [], 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for record, was_cached in pool.map(check, paths):
            records.append(record)
            reused += was_cached
            if len(records) % 2000 == 0:
                save(checkpoint, {"files": records, "vanished": []})
                print(json.dumps({"verified": len(records), "of": len(paths), "reused_hashes": reused}), flush=True)
    value = {"version": 1, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "roots": {k: str(v) for k, v in ROOTS.items()}, "files": records,
             "vanished_during_inventory": [], "total_bytes": sum(r["size"] for r in records)}
    save(run / "manifest.json", value)
    print(json.dumps({"status": "manifest_complete", "files": len(records), "bytes": value["total_bytes"]}), flush=True)


def pack(run):
    source = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    matched = json.loads((run / "remote-match.json").read_text(encoding="utf-8"))
    if matched["manifest_sha256"] != digest(run / "manifest.json"):
        raise RuntimeError("Remote matching receipt belongs to a different manifest")
    missing = set(matched["missing"])
    records = [r for r in source["files"] if r["id"] in missing]
    archive = run / "missing.tar.gz"
    if archive.exists():
        raise RuntimeError("Archive already exists; inspect before replacing")
    def prepare(record):
        path = Path(record["local"])
        state = path.stat()
        if (state.st_size, state.st_mtime_ns) != (record["size"], record["mtime_ns"]):
            raise RuntimeError(f"Changed file before packing: {path}")
        data = path.read_bytes() if state.st_size <= 2 * 1024 * 1024 else None
        after = path.stat()
        if (state.st_size, state.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f"Changed while reading: {path}")
        return record, data
    with tarfile.open(archive, "x:gz", compresslevel=1) as output, ThreadPoolExecutor(max_workers=8) as pool:
        queue = collections.deque()
        remaining = iter(records)
        for _ in range(min(32, len(records))):
            queue.append(pool.submit(prepare, next(remaining)))
        i = 0
        while queue:
            record, data = queue.popleft().result()
            following = next(remaining, None)
            if following is not None:
                queue.append(pool.submit(prepare, following))
            path = Path(record["local"])
            info = tarfile.TarInfo(record["id"])
            info.size, info.mtime, info.mode = record["size"], record["mtime_ns"] / 1e9, 0o600
            with (io.BytesIO(data) if data is not None else path.open("rb")) as stream:
                output.addfile(info, stream)
            if i % 500 == 0:
                print(json.dumps({"packed": i + 1, "of": len(records)}), flush=True)
            i += 1
    receipt = {"file": str(archive), "sha256": digest(archive), "bytes": archive.stat().st_size,
               "files": len(records), "uncompressed_bytes": sum(r["size"] for r in records)}
    save(run / "upload.json", receipt)
    print(json.dumps(receipt), flush=True)


def refresh(run):
    """Reuse completed hashes while reconciling a concurrent duplicate-archive cleanup."""
    original = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    prior = {r["local"]: r for r in original["files"]}
    current = []
    for label, root in ROOTS.items():
        if not root.exists():
            continue
        for base, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if d != ".git" and not (Path(base) / d).is_symlink()
                       and (Path(base) / d).resolve() != run.resolve()]
            for name in names:
                path = Path(base) / name
                state = path.stat()
                old = prior.get(str(path))
                if old and (state.st_size, state.st_mtime_ns) == (old["size"], old["mtime_ns"]):
                    current.append(old)
                    continue
                sha = digest(path)
                after = path.stat()
                if (state.st_size, state.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise RuntimeError(f"File changed during refresh: {path}")
                current.append({"id": label + "/" + path.relative_to(root).as_posix(),
                                "local": str(path), "size": after.st_size,
                                "mtime_ns": after.st_mtime_ns, "sha256": sha})
    current_by_path = {r["local"]: r for r in current}
    removed = set(prior) - set(current_by_path)
    removed.update(original.get("vanished_during_inventory", []))
    if removed:
        audit = json.loads(Path(r"E:\ChatGPT\Results\storage-cleanup-20261025\verified-archives.json").read_text())
        assert Path(audit["root"]) == ROOTS["results"]
        verified = {r["archive"]: r for r in audit["records"] if r["status"] == "verified_redundant"}
        for path in removed:
            if path not in verified:
                raise RuntimeError(f"Unexplained concurrent deletion: {path}")
            for saved in verified[path]["retained_files"]:
                retained = current_by_path.get(saved["path"])
                if not retained or retained["sha256"] != saved["sha256"] or retained["size"] != saved["bytes"]:
                    raise RuntimeError(f"Removed archive content lacks verified coverage: {saved['path']}")
    original.update(files=current, roots={k: str(v) for k, v in ROOTS.items()},
                    total_bytes=sum(r["size"] for r in current),
                    duplicate_archives_removed_by_concurrent_cleanup=sorted(removed),
                    vanished_during_inventory=[])
    save(run / "manifest.json", original)
    print(json.dumps({"status": "refreshed", "files": len(current),
                      "bytes": original["total_bytes"], "verified_duplicate_archives_removed": len(removed)}), flush=True)


def cleanup(run, execute):
    source = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    verified = json.loads((run / "remote-verified.json").read_text(encoding="utf-8"))
    if verified.get("status") != "PASS" or verified["manifest_sha256"] != digest(run / "manifest.json"):
        raise RuntimeError("Full remote verification is required")
    if verified["verified_files"] != len(source["files"]):
        raise RuntimeError("Incomplete remote coverage")
    records = []
    for r in source["files"]:
        label, rel = r["id"].split("/", 1)
        if label != "project" or rel.split("/")[0] in {"analysis", "packages", ".runtime", "__pycache__"}:
            path = Path(r["local"])
            root = ROOTS[label].resolve()
            resolved = path.resolve()
            if not resolved.is_relative_to(root) or resolved == root:
                raise RuntimeError(f"Unsafe deletion target: {resolved}")
            records.append(r)
    # The manifest's content hashes have been checked on Grace. Require unchanged
    # local size/timestamp for every deletion; abort before deleting any changed file.
    for i, r in enumerate(records):
        path = Path(r["local"])
        if path.exists():
            state = path.stat()
            if (state.st_size, state.st_mtime_ns) != (r["size"], r["mtime_ns"]):
                raise RuntimeError(f"File changed after upload: {path}")
        if i % 3000 == 0:
            print(json.dumps({"predelete_verified": i + 1, "of": len(records)}), flush=True)
    plan = {"execute": execute, "files": len(records), "bytes": sum(r["size"] for r in records),
            "remote": verified["snapshot"], "status": "PREVERIFIED"}
    save(run / "cleanup-plan.json", plan)
    if not execute:
        print(json.dumps(plan), flush=True)
        return
    deleted, absent, freed = 0, 0, 0
    with open(run / "deleted.jsonl", "a", encoding="utf-8") as log:
        for r in records:
            path = Path(r["local"])
            try:
                state = path.stat()
            except FileNotFoundError:
                absent += 1
                continue
            if (state.st_size, state.st_mtime_ns) != (r["size"], r["mtime_ns"]):
                raise RuntimeError(f"Changed since verification: {path}")
            path.unlink()
            log.write(json.dumps({"id": r["id"], "bytes": r["size"]}) + "\n")
            deleted += 1
            freed += r["size"]
    # Remove only empty directories inside the explicitly named roots.
    candidates = [v for k, v in ROOTS.items() if k != "project"]
    candidates += [PROJECT / d for d in ("analysis", "packages", ".runtime", "__pycache__")]
    for root in candidates:
        if not root.exists():
            continue
        for base, dirs, names in os.walk(root, topdown=False, followlinks=False):
            path = Path(base)
            if not path.resolve().is_relative_to(root.resolve()):
                raise RuntimeError(f"Unsafe empty-directory target: {path}")
            try:
                path.rmdir()
            except OSError:
                pass
    result = {"status": "COMPLETE", "deleted_files": deleted, "already_absent_files": absent,
              "freed_bytes": freed, "remote": verified["snapshot"],
              "manifest_sha256": verified["manifest_sha256"]}
    save(run / "cleanup-complete.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["inventory", "manifest", "manifest-fast", "refresh", "pack", "cleanup"])
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    args.run.mkdir(parents=True, exist_ok=True)
    if args.action == "inventory":
        inventory(args.run)
    elif args.action == "manifest":
        manifest(args.run)
    elif args.action == "manifest-fast":
        manifest_fast(args.run)
    elif args.action == "refresh":
        refresh(args.run)
    elif args.action == "pack":
        pack(args.run)
    else:
        cleanup(args.run, args.execute)
