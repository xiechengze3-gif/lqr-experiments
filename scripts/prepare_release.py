"""Build a small immutable source archive without simulation or installations."""
import hashlib
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
relative_files = ["lqr_experiments.py", "summarize.py", "README.md", "requirements.txt",
                  "configs/pilot.json", "slurm/experiment.sbatch", "scripts/submit_grace.sh",
                  "scripts/prepare_release.py", "source/project2_paper_body.tex"]
lines = []
for name in relative_files:
    data = (root / name).read_bytes()
    lines.append(f"{hashlib.sha256(data).hexdigest()}  {name}\n")
checksums = "".join(lines)
(root / "SHA256SUMS").write_text(checksums, encoding="utf-8", newline="\n")
release_id = hashlib.sha256(checksums.encode()).hexdigest()[:16]
archive = root / "packages" / f"lqr-{release_id}.tar.gz"
archive.parent.mkdir(exist_ok=True)
with tarfile.open(archive, "w:gz") as handle:
    for name in [*relative_files, "SHA256SUMS"]:
        handle.add(root / name, arcname=name)
print(f"RELEASE_ID={release_id}")
print(f"ARCHIVE={archive}")
print(f"SHA256={hashlib.sha256(archive.read_bytes()).hexdigest()}")
