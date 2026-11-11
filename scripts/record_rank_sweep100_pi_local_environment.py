"""Record actual local analysis paths and dependencies; no simulation."""
import argparse
from datetime import datetime, timezone
import importlib.metadata as metadata
import os
from pathlib import Path
import platform
import shutil
import sys

from publish_rank_sweep100_results import read, write


p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
p.add_argument('--phase',choices=['Pilot','Final'],required=True);p.add_argument('--elapsed-seconds',type=float)
a=p.parse_args();out=a.output.resolve();target=out/'local_reanalysis_environment.json'
keys=('TEMP','TMP','TMPDIR','XDG_CACHE_HOME','NUMBA_CACHE_DIR','MPLCONFIGDIR',
      'OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS')
env={key:os.environ[key] for key in keys}
for key in ('TEMP','TMP','TMPDIR','XDG_CACHE_HOME','NUMBA_CACHE_DIR','MPLCONFIGDIR'):
    assert Path(env[key]).resolve().drive.upper()=='E:',(key,env[key])
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS'):
    assert env[key]=='1'
assert out.drive.upper()=='E:'
d=read(target) if target.exists() else {}
d.update(python_executable=sys.executable,python_version=sys.version,platform=platform.platform(),
    output_directory=str(out),environment=env,
    installed_distributions={name:metadata.version(name) for name in
        ('numpy','scipy','numba','llvmlite','matplotlib','threadpoolctl')},
    free_bytes_on_E_at_last_inventory=shutil.disk_usage(out).free,
    new_primitive_transitions=0,
    scope='Independent saved-critic/policy audit, statistics and figures on E:. No new learned policy trajectories or simulator observations.')
event=dict(phase=a.phase,utc=datetime.now(timezone.utc).isoformat(),
           state='started' if a.elapsed_seconds is None else 'completed')
if a.elapsed_seconds is not None:event['elapsed_wall_seconds']=a.elapsed_seconds
d.setdefault('analysis_events',[]).append(event);write(target,d)
print(dict(output=str(out),cache=env['XDG_CACHE_HOME'],temporary=env['TMPDIR'],event=event),flush=True)
