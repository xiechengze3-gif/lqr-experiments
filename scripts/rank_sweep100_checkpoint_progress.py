"""Read only atomic checkpoint metadata; no NumPy, model evaluation or simulation."""
import argparse
import ast
from collections import Counter
import json
import re
import struct
from pathlib import Path
import zipfile

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/scratch/user/changze/lqr_experiments/results/rank-sweep100-confirm-20261016'))
p.add_argument('--phase',choices=['pilot','confirm'],default='confirm');p.add_argument('--details',action='store_true');a=p.parse_args()
seeds=set(range(5) if a.phase=='pilot' else range(100,130));stages=[];counts=[];details=[]
for path in (a.root/'checkpoints').glob('npg-*.npz'):
    match=re.fullmatch(r'npg-r(\d+)-s(\d+)\.npz',path.name)
    if match is None or int(match.group(2)) not in seeds:continue
    # save_npz closes its temporary ZIP before os.replace. An opened snapshot
    # remains immutable on Linux while later complete snapshots replace its name.
    with zipfile.ZipFile(path) as archive:blob=archive.read('meta.npy')
    assert blob[:6]==b'\x93NUMPY'
    size=2 if blob[6]==1 else 4;offset=8+size
    length=int.from_bytes(blob[8:offset],'little')
    header=ast.literal_eval(blob[offset:offset+length].decode('latin1'))
    assert header['descr'].startswith('<U')
    meta=json.loads(blob[offset+length:].decode('utf-32le').rstrip('\0'))
    stages.append(meta['next_stage']);counts.extend(meta['actual'].values())
    details.append(dict(rank=int(match.group(1)),seed=int(match.group(2)),stage=meta['next_stage']))
result=dict(phase=a.phase,checkpoint_files=len(stages),planned_pairs=5*len(seeds),
    stage_histogram=dict(sorted(Counter(stages).items())),
    min_recorded_transitions=min(counts) if counts else 0,max_recorded_transitions=max(counts) if counts else 0,
    note='Stage metadata only; completed checkpoints include any recorded failed paths.')
if a.details:result['least_advanced_examples']=sorted(details,key=lambda x:(x['stage'],x['rank'],x['seed']))[:10]
print(json.dumps(result))
