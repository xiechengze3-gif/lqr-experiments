"""Local stdlib integrity/coverage only; never performs scientific evaluation."""
import argparse
import ast
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path)
    a=p.parse_args()
    for line in (ROOT/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        digest,name=line.split('  ',1);assert sha(ROOT/name)==digest,name
    sources=list(ROOT.glob('*.py'))
    for source in sources:ast.parse(source.read_text(encoding='utf-8-sig'),filename=str(source))
    config=json.loads((ROOT/'config-X6a-v2.json').read_text())
    assert len(config['resource_tasks'])==8 and len(config['formal_tasks'])==40
    cells=[spec for task in config['formal_tasks'] for spec in task['cells']]
    identities=[tuple(s[k] for k in ['role','family','n','system','seed']) for s in cells]
    assert len(identities)==len(set(identities))==320
    assert Counter(s['role'] for s in cells)==dict(formal=256,calibration=64)
    if a.report:
        report=json.loads((a.report/'verification.json').read_text())
        assert report['status']=='COMPLETE'
        assert report['config_sha256']==sha(ROOT/'config-X6a-v2.json')
        for name,digest in report['files'].items():assert sha(a.report/name)==digest,name
        with (a.report/'observations.csv').open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f))
        assert len(rows)==12800
        keys=[tuple(r[k] for k in ['role','family','n','system','seed','N','algorithm','arm']) for r in rows]
        assert len(keys)==len(set(keys))
        for row in rows:
            N=int(row['N']);expected=N+512 if row['algorithm']=='CE' else (
                N+17)*config['horizon'][row['family']]
            assert int(row['actual_transitions'])==expected
        with (a.report/'calibration.csv').open(encoding='utf-8',newline='') as f:
            calibration=list(csv.DictReader(f))
        assert len(calibration)==24
        for row in calibration:
            assert row['status'] in ['QUALIFIED','RIGHT_CENSORED']
            assert row['smallest_N'] or row['censored_above_N']==str(max(config['stein_blocks_by_n'][row['n']]))
    print(json.dumps(dict(status='PASS_STATIC_AND_COVERAGE' if a.report else 'PASS_STATIC_ONLY',
                          numerical_validation=False,source_files_parsed=len(sources),
                          resource_tasks=8,formal_cells=320,formal_plus_calibration_paths=320)))


if __name__=='__main__':main()
