"""Package a reviewed dense study. This command runs no simulation."""
import hashlib
import tarfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
files=["dense_scaling.py","dense_report.py","slurm/dense_study.sbatch",
       "scripts/submit_dense.sh","scripts/prepare_dense_release.py","docs/DENSE_STUDY_PROTOCOL.md",
       *[f"configs/dense_{profile}.json" for profile in ("validation","scaling","approximate","actor")],
       "configs/dense_isotropic_scaling.json","configs/dense_isotropic_actor.json","docs/ISOTROPIC_STABILIZER_CONTROL.md",
       "source/project2_technical_notes_extracted.txt"]
checksums="".join(f"{hashlib.sha256((root/file).read_bytes()).hexdigest()}  {file}\n" for file in files)
(root/"DENSE_SHA256SUMS").write_text(checksums,encoding="utf-8",newline="\n")
release=hashlib.sha256(checksums.encode()).hexdigest()[:16]
archive=root/"packages"/f"dense-{release}.tar.gz"
with tarfile.open(archive,"w:gz") as t:
    for file in [*files,"DENSE_SHA256SUMS"]:
        t.add(root/file,arcname=file)
print(f"RELEASE_ID={release}\nARCHIVE={archive}\nSHA256={hashlib.sha256(archive.read_bytes()).hexdigest()}")
