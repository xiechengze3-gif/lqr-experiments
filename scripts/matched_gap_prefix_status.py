"""Lightweight saved-metadata status on prefixes available for EVERY formal seed.

No simulation, model evaluation, estimator fitting, or seed removal. This is not
the final independent numerical audit or its bootstrap confidence report.
"""
import argparse
import ast
import json
from pathlib import Path
import zipfile


def read_meta(path):
    with zipfile.ZipFile(path) as z:blob=z.read('meta.npy')
    assert blob[:6]==b'\x93NUMPY';size=2 if blob[6]==1 else 4;offset=8+size
    length=int.from_bytes(blob[8:offset],'little')
    header=ast.literal_eval(blob[offset:offset+length].decode('latin1'));assert header['descr'].startswith('<U')
    return json.loads(blob[offset+length:].decode('utf-32le').rstrip('\0'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--route',choices=['npg','pi'],required=True)
    a=p.parse_args();folder=a.root/a.route;c=json.loads((folder/'resolved_config.json').read_text());seeds=c['confirm_seeds'];result=[]
    for rank in c['ranks']:
        groups={};complete=0
        for seed in seeds:
            stem='{0}-r{1:03d}-s{2:04d}'.format(a.route,rank,seed);raw=folder/'raw'/(stem+'.json');cp=folder/'checkpoints'/(stem+'.npz')
            if raw.exists():d=json.loads(raw.read_text());records=d['records'];complete+=1
            elif cp.exists():records=read_meta(cp)['rows']
            else:continue
            groups[seed]={(r['method'],r['stage']):r for r in records}
        if len(groups)!=len(seeds):
            result.append(dict(rank=rank,started_pairs=len(groups),complete_full_pairs=complete,all_formal_seed_prefix_available=False));continue
        common=set.intersection(*(set(g) for g in groups.values()))
        for method in ('dense','truncated'):
            stages=sorted(stage for m,stage in common if m==method)
            for eps in (.1,.05):
                curve=[]
                for stage in stages:
                    rows=[groups[seed][method,stage] for seed in seeds];budget=rows[0]['transitions']
                    assert all(r['transitions']==budget for r in rows)
                    hits=sum(bool(r['observed'] and r['stable'] and r['whole_path_stable'] and r['gap'] is not None and r['gap']<=eps) for r in rows)
                    curve.append(dict(stage=stage,transitions=budget,successes=hits,seeds=len(seeds)))
                hit=next((r for r in curve if r['successes']/len(seeds)>=.9-1e-12),None)
                result.append(dict(rank=rank,method=method,epsilon=eps,seeds=len(seeds),complete_full_pairs=complete,
                    latest_common_stage=stages[-1],latest_common_budget=curve[-1]['transitions'],
                    N_hat_from_available_prefix=hit['transitions'] if hit else None,
                    successes_at_threshold=hit['successes'] if hit else None,
                    latest_common_successes=curve[-1]['successes']))
    print(json.dumps(dict(route=a.route,status='intermediate_saved_metadata_snapshot',results=result,
        caveat='Only prefixes available for all30 formal seeds are compared. Final cost/actor audit and bootstrap intervals remain in the scheduled full report. A missing threshold here is not a claim of not reached at the configured maximum.')))


if __name__=='__main__':main()
