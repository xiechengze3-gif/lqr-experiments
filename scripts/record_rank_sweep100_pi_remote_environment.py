"""Read dependency metadata on Grace; do not import numerical packages."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import sys

p=argparse.ArgumentParser();p.add_argument('--result',type=Path,required=True)
p.add_argument('--release',type=Path,required=True);a=p.parse_args()
fallback=Path('/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages')
sys.path.append(str(fallback));versions={}
for name in ('numpy','scipy','numba','llvmlite','matplotlib','threadpoolctl'):
    try:
        package=metadata.distribution(name)
        versions[name]=dict(version=package.version,metadata_location=str(package._path))
    except metadata.PackageNotFoundError:versions[name]=None
vendor=a.release/'threadpoolctl.py'
version=re.search(r'^__version__\s*=\s*[\"\']([^\"\']+)',vendor.read_text(),re.M).group(1)
result=dict(python_executable=sys.executable,python_version=sys.version,
    installed_distributions=versions,fallback_path=str(fallback),
    effective_threadpoolctl=dict(version=version,path=str(vendor),
        sha256=hashlib.sha256(vendor.read_bytes()).hexdigest()),
    scope='Metadata-only inventory using the production interpreter and fallback path. No numerical package imports, simulation, model evaluation, or dependency installation.')
(a.result/'runtime_dependency_metadata.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
