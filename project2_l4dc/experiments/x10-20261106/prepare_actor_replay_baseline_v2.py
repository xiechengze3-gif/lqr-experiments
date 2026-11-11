"""Verify/copy original replay arrays to a NEW X10-only input bundle; no numerics."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    config=json.loads((HERE/'actor-draft-v2/actor-config-protocol-v1.json').read_text())
    original=HERE.parent/'x6-20261101/X6b-protocol-v2/deliveries/formal-v1/X6b/formal-v1/n24-low-three/task-0'
    target=HERE/'actor-replay-baseline-v2';assert not target.exists()
    files={};sources={}
    for ref in config['original_replay']:
        folder=original/(ref['algorithm']+'-r0015625')
        data=(folder/'DONE.json').read_bytes();assert sha(data)==ref['sha256']
        done=json.loads(data)
        assert done['spec']==ref['spec']
        selected=[dict(path='DONE.json',sha256=ref['sha256'])]+done['artifacts']
        for item in selected:
            assert Path(item['path']).name==item['path']
            source=folder/item['path'];payload=source.read_bytes();assert sha(payload)==item['sha256']
            name=ref['algorithm']+'/'+item['path']
            files[name]=payload;sources[name]=dict(source=str(source),sha256=sha(payload),bytes=len(payload))
    assert len(files)==50  # two original DONE receipts plus 32 NPG /16 PI stage arrays
    target.mkdir()
    for name,data in files.items():
        path=target/name;path.parent.mkdir(exist_ok=True)
        with path.open('xb') as stream:stream.write(data)
        assert sha(path.read_bytes())==sources[name]['sha256']
    proof=dict(status='PASS_ORIGINAL_REPLAY_ARRAY_BYTES_PRESERVED_NEW_NAMESPACE',files=sources,
        original_receipts=2,original_stage_arrays=48,original_results_modified=False,
        new_training_transitions=0,new_jobs=0,SU=0,
        purpose='Prepared corrected-pilot reference input only. No authorization to rerun the failed pilot is inferred.')
    with (target/'MANIFEST_v2.json').open('x') as stream:json.dump(proof,stream,indent=2)
    print(json.dumps({k:v for k,v in proof.items() if k!='files'}))


if __name__=='__main__':main()
