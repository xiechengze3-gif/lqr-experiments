"""Copy saved failure metadata for new CE plots; source results stay untouched."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    experiments=HERE.parent
    paths={
      'X8_exact_raw.csv':experiments/'x8-local-20261104/x8_b_raw.csv',
      'X8_geometric_raw.csv':experiments/'x8-local-20261104/x8_c_raw.csv',
      'X6a_CE_observations.csv':experiments/'x6-20261101/CE-addition-v2/deliveries/ce-20365253-v7/X6a/CE-addition-v1/observations.csv'}
    target=HERE/'ce-report-inputs-v1';assert not target.exists();target.mkdir()
    rows={}
    for name,source in paths.items():
        data=source.read_bytes()
        with (target/name).open('xb') as stream:stream.write(data)
        rows[name]=dict(source=str(source),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
        assert source.read_bytes()==data
    proof=dict(status='SAVED_CE_FAILURE_RECORDS_COPIED_NO_COMPUTE',files=rows,old_results_edited=False,new_jobs=0,SU=0)
    with (target/'MANIFEST_v1.json').open('x') as stream:json.dump(proof,stream,indent=2)
    print(json.dumps(proof))


if __name__=='__main__':main()
