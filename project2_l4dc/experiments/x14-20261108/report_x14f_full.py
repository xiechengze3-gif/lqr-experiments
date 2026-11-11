"""Analyze the eight lower B* rungs and join the already-sealed B* top rung."""
import csv
import io
import json
import os
import tarfile
from pathlib import Path

import analyze_actor as analysis
import frozen_engine as engine
import report_products_v1 as products
from report_x14f import ArchivePath, NumpyReadProxy, json_write, read_csv, sha, write_csv
from virtual_task_store_v2 import file_sha, verify_archive


HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
CONFIG=HERE/'config-x14f-full-v1.json'


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
            stem=ROOT/f'x14f-full-formal-{index:03d}'
            final=json.loads(stem.with_suffix('.jsonl').read_bytes().splitlines()[-1])
            assert final['status']=='COMPLETE' and final['kind']=='TASK_FINAL' and final['index']==index
            assert final['group']['id']==group and final['config_sha256']==self.config_sha
            path=stem.with_suffix('.tar')
            assert path.stat().st_size==final['archive_bytes'] and file_sha(path)==final['archive_sha256']
            verify_archive(path,final['members'])
            self.current=tarfile.open(path,'r')
            self.index=index
        return self.current.extractfile('/'.join(name)).read()


def reindex_top(rows):
    assert all(float(r['rung'])==1.5625 for r in rows)
    return [dict(r,rung='1.0') for r in rows]


def replace_60(original,added,output):
    """Replace exactly the n=60 records and preserve every other physical line."""
    data=original.read_bytes()
    header,*lines=data.splitlines(keepends=True)
    rows=read_csv(original)
    assert len(rows)==len(lines) and data.endswith(b'\n')
    new=io.StringIO(newline='')
    schema=list(rows[0])
    assert all(set(row)==set(schema) for row in added)
    writer=csv.DictWriter(new,fieldnames=schema)
    writer.writerows(added)
    replacement=new.getvalue().encode('utf-8')
    before=[]
    combined=[header]
    changed=0
    for row,line in zip(rows,lines,strict=True):
        if int(float(row['n']))==60:
            if changed==0:
                combined.append(replacement)
            changed+=1
        else:
            before.append(line)
            combined.append(line)
    assert changed==len(added)
    with output.open('xb') as f:
        f.write(b''.join(combined))
    new_header,*new_lines=output.read_bytes().splitlines(keepends=True)
    new_rows=read_csv(output)
    assert new_header==header and len(new_rows)==len(rows)==len(new_lines)
    assert [line for row,line in zip(new_rows,new_lines,strict=True) if int(float(row['n']))!=60]==before
    return len(before)


def main():
    engine.require_compute()
    config=json.loads(CONFIG.read_bytes())
    assert file_sha(analysis.__file__)==config['scientific_sources']['analyze_actor.py']
    assert config['rungs']==[1/2**i for i in range(8,0,-1)]
    top=ROOT/'x14f-report'
    top_proof=json.loads((top/'REPORT_DONE.json').read_bytes())
    assert top_proof['item']=='f' and top_proof['status']=='COMPLETE_SAVED_DATA_REPORT'
    for filename,expected in top_proof['files'].items():
        assert file_sha(top/filename)==expected
    out=ROOT/'x14f-full-report'
    out.mkdir()
    internal=Path(os.environ['TMPDIR'])/'inspection'
    internal.mkdir()
    analysis.BASE=internal
    reader=Reader(config)
    prior=engine.sha,engine.save,analysis.np
    try:
        engine.sha,engine.save,analysis.np=sha,json_write,NumpyReadProxy()
        analysis.inspect(CONFIG,ArchivePath(reader),internal/'diagnostics-n60',60)
        analysis.summarize(CONFIG,internal,internal/'new')
    finally:
        engine.sha,engine.save,analysis.np=prior
        reader.close()
    summary=read_csv(internal/'new/summary.csv')+reindex_top(read_csv(top/'X14f_summary.csv'))
    assert len(summary)==36 and len({(r['algorithm'],r['rung'],r['ratio_kind']) for r in summary})==36
    assert {float(r['rung']) for r in summary}=={1/2**j for j in range(9)}
    summary.sort(key=lambda r:(r['algorithm']=='PI',float(r['rung']),r['ratio_kind']!='both_stable'))
    write_csv(out/'B60_summary.csv',summary,list(summary[0]))
    derived=products.derived(summary)
    write_csv(out/'B60_transitions_saved.csv',derived,list(derived[0]))
    source_summary=HERE/'X12_merged_original_summary.csv'
    source_transitions=HERE/'X12_merged_original_transitions.csv'
    nontarget_summary=replace_60(source_summary,summary,out/'X12_summary_merged_B60.csv')
    nontarget_transitions=replace_60(source_transitions,derived,out/'X12_transitions_saved_merged_B60.csv')
    assert (nontarget_summary,nontarget_transitions)==(144,8)
    raw={}
    for name,count in [('endpoints',1152),('stages',14976),('paired_endpoints',576)]:
        file=name+'.csv'
        data=read_csv(internal/'new'/file)+reindex_top(read_csv(top/file))
        assert len(data)==count
        write_csv(out/file,data,list(data[0]))
        raw[name]=data
    counts=[]
    for r in summary:
        if r['ratio_kind']=='failure_inclusive':
            counts.append(dict(n=60,algorithm=r['algorithm'],rung=r['rung'],primitive_per_arm=r['primitive_per_arm'],
                               full=32,dense_failures=32-int(r['dense_stable']),truncated_failures=32-int(r['truncated_stable'])))
    assert len(counts)==18
    write_csv(out/'failure_counts_by_cell.csv',counts,list(counts[0]))
    failed=[r for r in raw['endpoints'] if r['stable']=='False']
    assert len(failed)==sum(row['dense_failures']+row['truncated_failures'] for row in counts)
    write_csv(out/'failures.csv',failed,list(raw['endpoints'][0]))
    proof=dict(status='COMPLETE_SAVED_DATA_REPORT',item='f-full',job=os.environ['SLURM_ARRAY_JOB_ID'],
               config_sha256=file_sha(CONFIG),new_observation_transitions=0,summary_rows=36,
               endpoint_rows=1152,stage_rows=14976,reused_top_rung_endpoints=128,
               exact_non60_summary_rows=nontarget_summary,exact_non60_cross_rows=nontarget_transitions,
               files={p.name:file_sha(p) for p in out.iterdir()})
    json_write(out/'REPORT_DONE.json',proof)
    print(json.dumps(proof),flush=True)


if __name__=='__main__':
    main()
