"""Reuse audited CE/LSTD simulations and add NPG with explicit provenance.

Assembled records are a reporting dataset, not a new joint simulation release.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    temp.replace(path)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--original-manifest',required=True,type=Path)
    p.add_argument('--npg-manifest',required=True,type=Path)
    p.add_argument('--original',required=True,type=Path)
    p.add_argument('--npg',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    cfg=json.loads(a.manifest.read_text())
    originals=[json.loads(x.read_text()) for x in (a.original_manifest,a.npg_manifest)]
    common={k:v for k,v in cfg.items() if k!='algorithms'}
    assert all({k:v for k,v in x.items() if k!='algorithms'}==common for x in originals)
    assert cfg['algorithms']==['CE','LSTD_PI','NPG']
    sources={}
    for name,manifest,root,algorithms in (
        ('ce_lstd',a.original_manifest,a.original,['CE','LSTD_PI']),
        ('npg',a.npg_manifest,a.npg,['NPG'])):
        completion=json.loads((root/'completion.json').read_text())
        assert completion['status']=='COMPLETE'
        assert completion['task_ids']==[t['id'] for t in cfg['tasks']]
        assert completion['identity']['manifest_sha256']==sha(manifest)
        sources[name]=dict(root=str(root),identity=completion['identity'],algorithms=algorithms)
    assert sources['ce_lstd']['identity']['sources']==sources['npg']['identity']['sources'], 'Scientific source changes require a separate comparability review'
    joint_identity=dict(manifest_sha256=sha(a.manifest),assembly_source_sha256=sha(__file__),
        type='assembled_reporting_dataset',components=sources)
    for task in cfg['tasks']:
        records,files,matrices=[],{},None
        for name,root,algorithms in (('ce_lstd',a.original,['CE','LSTD_PI']),('npg',a.npg,['NPG'])):
            path=root/'raw'/f"task-{task['id']:03d}.json"
            payload=json.loads(path.read_text())
            assert payload['task']==task and payload['identity']==sources[name]['identity']
            if matrices is None: matrices=payload['system']
            assert payload['system']==matrices, 'Reused simulations have different systems'
            part=[r for r in payload['records'] if r['algorithm'] in algorithms]
            expected=len(algorithms)*len(cfg['methods'])*(2*len(cfg['fixed_budgets'])+len(cfg['schedule'])+1)
            assert len(part)==expected
            records.extend(dict(r,component_manifest_sha256=payload['identity']['manifest_sha256']) for r in part)
            files[name]=dict(path=str(path),sha256=sha(path))
        save(a.output/'raw'/f"task-{task['id']:03d}.json",dict(task=task,identity=joint_identity,
            system=matrices,records=records,component_files=files,
            execution=dict(mode='assembled_report',ce_lstd_simulations_reused=True,
                           npg_simulations_new=True,slurm_job_id=None)))
    save(a.output/'completion.json',dict(status='COMPLETE',identity=joint_identity,
        task_ids=[t['id'] for t in cfg['tasks']],new_simulated_algorithms=['NPG'],
        reused_algorithms=['CE','LSTD_PI']))
    print(json.dumps(dict(status='COMPLETE',tasks=len(cfg['tasks']),output=str(a.output))))


if __name__=='__main__':
    main()
