"""Dependency metadata only; safe lightweight inventory without importing numerics."""
import hashlib
import importlib.metadata as metadata
import json
import re
import sys
from pathlib import Path

fallback=Path('/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages')
sys.path.append(str(fallback))
root=Path('/scratch/user/changze/lqr_experiments')
release=root/'releases/rank-sweep100-confirm-20261016'
versions={}
for name in ('numpy','scipy','numba','llvmlite','matplotlib','threadpoolctl'):
    try:
        package=metadata.distribution(name)
        versions[name]=dict(version=package.version,metadata_location=str(package._path))
    except metadata.PackageNotFoundError:versions[name]=None
vendor=release/'threadpoolctl.py'
version=re.search(r'^__version__\s*=\s*[\"\']([^\"\']+)',vendor.read_text(),re.M).group(1)
result=dict(python_executable=sys.executable,python_version=sys.version,
    installed_distributions=versions,
    effective_threadpoolctl=dict(version=version,path=str(vendor),sha256=hashlib.sha256(vendor.read_bytes()).hexdigest()),
    fallback_path=str(fallback),
    scope='Read distribution metadata using the experiment interpreter and fallback path; no numerical modules, simulation or model evaluation were imported. Runtime threadpools are saved in verification benchmarks.')
path=root/'results/rank-sweep100-confirm-20261016/runtime_dependency_metadata.json'
path.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
