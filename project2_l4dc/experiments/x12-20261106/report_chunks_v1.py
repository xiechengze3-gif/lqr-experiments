"""Hash-sealed fixed-size transport chunks for an existing complete report archive."""
import argparse,hashlib,json
from pathlib import Path
SIZE=128*1024*1024
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()

def split():
    tmp=Path('/scratch/user/changze/lqr_experiments/tmp/x12-20261106')
    archive=tmp/'x12-report-v1.tar.gz';manifest=archive.with_suffix('.json')
    source=json.loads(manifest.read_text());assert source['status']=='SEALED_X12_COMPLETE_DELIVERY'
    assert sha(archive)==source['archive_sha256']
    dest=tmp/'x12-report-parts-v1';assert not dest.exists();dest.mkdir()
    with (dest/'BEGIN.json').open('x') as f:json.dump(dict(archive=str(archive),archive_sha256=source['archive_sha256'],chunk_bytes=SIZE),f)
    entries=[]
    with archive.open('rb') as src:
        i=0
        while True:
            block=src.read(SIZE)
            if not block:break
            name='part-'+str(i).zfill(4)+'.bin';p=dest/name
            with p.open('xb') as out:out.write(block)
            entries.append(dict(name=name,offset=i*SIZE,bytes=len(block),sha256=hashlib.sha256(block).hexdigest()));i+=1
    result=dict(status='SEALED_REPORT_TRANSPORT_CHUNKS',archive_bytes=archive.stat().st_size,archive_sha256=source['archive_sha256'],
        original_manifest_sha256=sha(manifest),chunk_bytes=SIZE,chunks=entries,source_sha256=sha(Path(__file__)),
        original_archive_unchanged=True,numerical_reanalysis=False,new_transitions=0)
    assert sum(x['bytes'] for x in entries)==result['archive_bytes']
    with (dest/'DONE.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='chunks'}))

def assemble(parts,manifest,target):
    proof=json.loads(manifest.read_text());assert proof['status']=='SEALED_REPORT_TRANSPORT_CHUNKS'
    assert not target.exists()
    expected_offset=0
    for i,x in enumerate(proof['chunks']):
        assert x['name']=='part-'+str(i).zfill(4)+'.bin' and x['offset']==expected_offset
        p=parts/x['name'];assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256'];expected_offset+=x['bytes']
    assert expected_offset==proof['archive_bytes']
    with target.open('xb') as dst:
        for x in proof['chunks']:
            with (parts/x['name']).open('rb') as src:
                for block in iter(lambda:src.read(1024*1024),b''):dst.write(block)
    assert target.stat().st_size==proof['archive_bytes'] and sha(target)==proof['archive_sha256']
    result=dict(status='ASSEMBLED_BYTE_IDENTICAL_FULL_REPORT_ARCHIVE',archive_sha256=proof['archive_sha256'],archive_bytes=proof['archive_bytes'],
        chunks=len(proof['chunks']),new_transitions=0,numerical_reanalysis=False)
    with target.with_suffix('.assembly-verified.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['split','assemble']);p.add_argument('--parts',type=Path);p.add_argument('--manifest',type=Path);p.add_argument('--target',type=Path);a=p.parse_args()
    if a.mode=='split':split()
    else:assemble(a.parts,a.manifest,a.target)
