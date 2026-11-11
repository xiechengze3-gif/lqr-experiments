"""Run the original X12 saved-data analyzer on a new one-rung archive grid."""
import ast
import csv
import hashlib
import io
import json
import math
import os
import tarfile
from pathlib import Path, PurePosixPath

import numpy as np

import analyze_actor as analysis
import frozen_engine as engine
from paper_cross import cross
from virtual_task_store_v2 import file_sha, verify_archive


HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
CONFIG=HERE/'config-x14f-v1.json'


class ArchivePath:
    def __init__(self,reader,path=PurePosixPath('.')):
        self.reader,self.path=reader,path

    def __truediv__(self,name):
        return type(self)(self.reader,self.path/name)

    def read_bytes(self):
        return self.reader.read(self.path)

    def read_text(self,encoding='utf-8'):
        return self.read_bytes().decode(encoding)


class Reader:
    def __init__(self,config):
        self.groups={g['id']:i for i,g in enumerate(config['formal_groups'])}
        self.current=None
        self.index=None
        self.config_sha=file_sha(CONFIG)

    def close(self):
        if self.current is not None:
            self.current.close()

    def read(self,path):
        group,task,*name=path.parts
        index=self.groups[group]*32+int(task.removeprefix('task-'))
        if self.index!=index:
            self.close()
            stem=ROOT/f'x14f-formal-{index:03d}'
            final=json.loads(stem.with_suffix('.jsonl').read_bytes().splitlines()[-1])
            assert final['status']=='COMPLETE' and final['kind']=='TASK_FINAL' and final['index']==index
            assert final['group']['id']==group and final['config_sha256']==self.config_sha
            path=stem.with_suffix('.tar')
            assert path.stat().st_size==final['archive_bytes'] and file_sha(path)==final['archive_sha256']
            verify_archive(path,final['members'])
            self.current=tarfile.open(path,'r')
            self.index=index
        return self.current.extractfile('/'.join(name)).read()


class NumpyReadProxy:
    def __getattr__(self,name):
        return getattr(np,name)

    def load(self,path,*args,**kwargs):
        if isinstance(path,ArchivePath):
            path=io.BytesIO(path.read_bytes())
        return np.load(path,*args,**kwargs)


def sha(path):
    if isinstance(path,ArchivePath):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return file_sha(path)


def json_write(path,value):
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2)


def read_csv(path):
    with path.open(newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write_csv(path,rows,fields):
    with path.open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def derived_ten_rungs(summary):
    path=HERE/'report_products_v1.py'
    module=ast.parse(path.read_bytes())
    function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='derived')
    # Lift the X12 rung-count guard and metadata to the ten-point ladder.
    counts=[node for node in ast.walk(function) if isinstance(node,ast.Constant) and node.value==9]
    assert len(counts)==2
    for node in counts:
        node.value=10
    env=dict(np=np,math=math,cross=cross)
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(path),'exec'),env)
    return env['derived'](summary)


def main():
    engine.require_compute()
    config=json.loads(CONFIG.read_bytes())
    source=config['scientific_sources']
    assert file_sha(analysis.__file__)==source['analyze_actor.py']
    assert config['rungs']==[1.5625]
    out=ROOT/'x14f-report'
    out.mkdir()
    internal=Path(os.environ['TMPDIR'])/'inspection'
    internal.mkdir()
    analysis.BASE=internal
    reader=Reader(config)
    old=engine.sha,engine.save,analysis.np
    try:
        engine.sha,engine.save,analysis.np=sha,json_write,NumpyReadProxy()
        analysis.inspect(CONFIG,ArchivePath(reader),internal/'diagnostics-n60',60)
        analysis.summarize(CONFIG,internal,internal/'new')
    finally:
        engine.sha,engine.save,analysis.np=old
        reader.close()
    new=read_csv(internal/'new/summary.csv')
    prior=read_csv(HERE/'X12_n60_nine_rungs_summary.csv')
    assert len(new)==4 and len(prior)==36 and set(new[0])==set(prior[0])
    assert all(float(r['rung'])==1.5625 for r in new)
    summary_path=out/'X14f_summary.csv'
    write_csv(summary_path,new,list(prior[0]))
    merged=out/'X14f_summary_with_X12_nine_rungs.csv'
    with merged.open('xb') as f:
        source_bytes=(HERE/'X12_n60_nine_rungs_summary.csv').read_bytes()
        assert source_bytes.endswith(b'\n')
        f.write(source_bytes+summary_path.read_bytes().split(b'\n',1)[1])
    rows=read_csv(merged)
    assert len(rows)==40
    result=derived_ten_rungs(rows)
    write_csv(out/'X14f_transitions_saved_derived.csv',result,list(result[0]))
    for filename in ('endpoints.csv','stages.csv','paired_endpoints.csv'):
        with (out/filename).open('xb') as f:
            f.write((internal/'new'/filename).read_bytes())
    endpoints=read_csv(out/'endpoints.csv')
    stages=read_csv(out/'stages.csv')
    assert len(endpoints)==128 and len(stages)==1664
    write_csv(out/'failures.csv',[r for r in endpoints if r['stable']=='False'],list(endpoints[0]))
    proof=dict(status='COMPLETE_SAVED_DATA_REPORT',item='f',job=os.environ['SLURM_ARRAY_JOB_ID'],
               config_sha256=file_sha(CONFIG),new_observation_transitions=0,new_summary_rows=4,
               endpoint_rows=len(endpoints),stage_rows=len(stages),
               files={p.name:file_sha(p) for p in out.iterdir()})
    json_write(out/'REPORT_DONE.json',proof)
    print(json.dumps(proof),flush=True)


if __name__=='__main__':
    main()
