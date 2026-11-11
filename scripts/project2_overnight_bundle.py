"""Run unchanged independent logical tasks in bounded sequential Slurm bundles."""
import argparse
import json
from pathlib import Path
import sys
import time

RELEASE=Path('/scratch/user/changze/lqr_experiments/releases/project2-overnight-20261020')
sys.path[:0]=[str(RELEASE/'scripts'),str(RELEASE)]
import project2_overnight as science


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--index',type=int,required=True)
    parser.add_argument('--size',type=int,default=12)
    args=parser.parse_args();science.require_compute()
    cfg=json.loads(args.manifest.read_text());out=Path(cfg['output'])
    identity=science.sha(args.manifest)+'|'+science.sha(science.__file__)
    low=args.index*args.size;high=min(len(cfg['mechanism_tasks']),low+args.size)
    assert low<high
    begin=time.monotonic()
    for i in range(low,high):
        science.mechanism_task(cfg['mechanism_tasks'][i],out,identity)
    science.atomic_json(out/'bundles'/f'bundle-{args.index:03d}.json',
        dict(status='complete',first=low,last=high-1,count=high-low,
             seconds=time.monotonic()-begin,identity=identity))


if __name__=='__main__':main()
