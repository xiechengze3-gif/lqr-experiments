"""Promote fully written Windows checkpoint temporaries after workers exit.

No sampling, policy updates, RNG consumption or scientific changes occur here.
Run only after the original experiment process has returned.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import numpy as np


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main(output):
    out=Path(output);ident=json.loads((out/'frozen/identity.json').read_text())
    recovered=[]
    for temp in sorted((out/'checkpoints').glob('*.tmp')):
        final=temp.with_suffix('.npz')
        with np.load(temp,allow_pickle=False) as new, np.load(final,allow_pickle=False) as old:
            assert json.loads(str(new['identity']))==ident==json.loads(str(old['identity']))
            old_stage,new_stage=int(old['next_stage']),int(new['next_stage'])
            assert new_stage==old_stage+1,(temp,old_stage,new_stage)
            prior=json.loads(str(old['rows']));rows=json.loads(str(new['rows']))
            assert rows[:-1]==prior and len(rows)==new_stage+1
            np.testing.assert_array_equal(new['policies'][:-1],old['policies'])
            np.testing.assert_array_equal(new['policies'][-1],new['K'])
            assert int(new['actual'])==rows[-1]['actual_transitions']
            record=dict(checkpoint=str(final),old_stage=old_stage,recovered_stage=new_stage,
                        actual_transitions=int(new['actual']),temporary_sha256=sha(temp),
                        old_checkpoint_sha256=sha(final),
                        K_sha256=hashlib.sha256(new['K'].tobytes()).hexdigest(),
                        continuous_state_sha256=hashlib.sha256(new['x'].tobytes()).hexdigest())
        os.replace(temp,final)
        assert sha(final)==record['temporary_sha256']
        recovered.append(record)
    receipt=dict(status='PASS',identity=ident,recovered=recovered,
                 explanation='Fully written checkpoint archives retained after Windows file replacement was blocked. Promoted after workers exited; no reset, resampling or new optimizer step.',
                 source_sha256=sha(Path(__file__)))
    destination=out/'checkpoint_recovery.json'
    assert not destination.exists(),'Do not overwrite an existing recovery receipt'
    destination.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.output)
