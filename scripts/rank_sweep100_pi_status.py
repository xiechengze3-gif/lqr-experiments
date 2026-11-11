"""Compact operational PI progress from immutable checkpoint metadata only."""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import re
import zipfile

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
p.add_argument('--phase',choices=['pilot','confirm'],default='pilot')
p.add_argument('--diagnostic-seed',type=int);p.add_argument('--temporary-root',type=Path);a=p.parse_args()
seeds={a.diagnostic_seed} if a.diagnostic_seed is not None else set(range(5) if a.phase=='pilot' else range(100,130))
stages=[];failed=[];completed=0;counts=[];completed_by_rank=Counter()
for path in (a.root/'checkpoints').glob('pi-*.npz'):
    match=re.fullmatch(r'pi-r(\d+)-s(\d+)\.npz',path.name)
    if not match or int(match.group(2)) not in seeds:continue
    with zipfile.ZipFile(path) as archive:blob=archive.read('meta.npy')
    assert blob[:6]==b'\x93NUMPY';size=2 if blob[6]==1 else 4;offset=8+size
    length=int.from_bytes(blob[8:offset],'little');header=ast.literal_eval(blob[offset:offset+length].decode('latin1'))
    assert header['descr'].startswith('<U')
    meta=json.loads(blob[offset+length:].decode('utf-32le').rstrip('\0'))
    stages.append(meta['next_stage']);counts.extend(meta['actual'].values())
    failed.extend(meta['failed'].values())
for path in (a.root/'raw').glob('pi-*.json'):
    match=re.fullmatch(r'pi-r(\d+)-s(\d+)\.json',path.name)
    if match and int(match.group(2)) in seeds:
        completed+=1;completed_by_rank[int(match.group(1))]+=1
pending=[]
if a.temporary_root:
    for path in a.temporary_root.glob('pi-r*-s*/stage-*/collection.json'):
        match=re.fullmatch(r'pi-r(\d+)-s(\d+)',path.parent.parent.name)
        if not match or int(match.group(2)) not in seeds:continue
        meta=json.loads(path.read_text())
        pending.append(dict(rank=int(match.group(1)),seed=int(match.group(2)),stage_method=path.parent.name,
                            filled=meta['filled'],actual=meta['actual'],fit_complete=(path.parent/'fit.json').exists()))
result=dict(phase=a.phase,checkpoint_pairs=len(stages),completed_pairs=completed,
    completed_by_rank=dict(sorted(completed_by_rank.items())),
    stage_histogram=dict(sorted(Counter(stages).items())),recorded_failed_arms=sum(failed),
    min_recorded_transitions=min(counts) if counts else 0,max_recorded_transitions=max(counts) if counts else 0,
    note='Metadata-only progress; no new numerical work or true-system evaluation')
if a.temporary_root:result.update(pending_collectors=len(pending),pending_examples=pending[:12],
    pending_histogram=dict(Counter(p['stage_method']+(' fitted' if p['fit_complete'] else ' collecting_or_fitting') for p in pending)))
print(json.dumps(result))
