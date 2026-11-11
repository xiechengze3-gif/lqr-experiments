"""Windows native memory and E-drive paths; stdlib only, no scientific imports."""
import ctypes
import datetime
import json
import os
import shutil
import sys
from pathlib import Path


class Memory(ctypes.Structure):
    _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
        (name, ctypes.c_ulonglong) for name in ['total_physical', 'available_physical',
         'total_pagefile', 'available_pagefile', 'total_virtual', 'available_virtual',
         'available_extended_virtual']]


data = Memory()
data.length = ctypes.sizeof(data)
assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(data))
root = Path(__file__).resolve().parent
disk = shutil.disk_usage(root)
assert data.available_physical >= 4*1024**3, 'Need >=4GiB currently available physical memory.'
assert disk.free >= 4*1024**3, 'Need >=4GiB E-drive free space.'
assert Path(sys.executable).drive.upper() == 'E:'
paths = {key: os.environ[key] for key in ['TEMP', 'TMP', 'TMPDIR', 'XDG_CACHE_HOME', 'NUMBA_CACHE_DIR', 'MPLCONFIGDIR']}
assert all(Path(value).drive.upper() == 'E:' and Path(value).is_dir() for value in paths.values())
proof = dict(status='LOCAL_STORAGE_MEMORY_PREFLIGHT_PASS',
             checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             executable=sys.executable, physical_total_bytes=data.total_physical,
             physical_available_bytes=data.available_physical, E_free_bytes=disk.free,
             output_root=str(root), actual_environment_paths=paths,
             numerical_imports=False, installation=False)
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')
with (root/('local-preflight-'+stamp+'.json')).open('x') as stream:
    json.dump(proof, stream, indent=2)
print(json.dumps(proof), flush=True)
