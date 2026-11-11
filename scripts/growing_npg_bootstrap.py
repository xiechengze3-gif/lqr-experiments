"""Verify growing NPG, preserve unrelated results, and dispatch one worker."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');temporary.replace(path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--old-manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--old-output',type=Path,required=True)
    args=parser.parse_args()
    cfg=json.loads(args.manifest.read_text());old_cfg=json.loads(args.old_manifest.read_text())
    normalized=json.loads(json.dumps(cfg))
    for settings in normalized['profiles'].values():del settings['NPG']['batches']
    assert normalized==old_cfg
    args.output.mkdir(parents=True,exist_ok=True)
    from fixed_value_run import identity
    ident=identity(args.manifest)
    old_ident=json.loads((args.old_output/'verification.json').read_text())['identity']
    assert all(value==old_ident['sources'][key] for key,value in ident['sources'].items()
               if key!='scripts/fixed_value_run.py')
    status=args.output/'bootstrap_status.json'
    save(status,dict(status='RUNNING',phase='verification'))
    proof=args.output/'verification.json'
    existing=json.loads(proof.read_text()) if proof.exists() else {}
    if existing.get('status')!='PASS' or existing.get('identity')!=ident:
        with (args.output/'verify.log').open('ab') as log:
            subprocess.run([sys.executable,'-B',str(Path(__file__).parent/'fixed_value_run.py'),'verify',
                '--manifest',str(args.manifest),'--output',str(args.output)],stdout=log,stderr=subprocess.STDOUT,check=True)
    compatibility=args.output/'compatibility_verification.json'
    existing=json.loads(compatibility.read_text()) if compatibility.exists() else {}
    if existing.get('status')!='PASS' or existing.get('identity')!=ident:
        with (args.output/'compatibility_verify.log').open('ab') as log:
            subprocess.run([sys.executable,'-B',str(Path(__file__).parent/'verify_growing_npg_compatibility.py'),
                '--manifest',str(args.manifest),'--old-manifest',str(args.old_manifest),
                '--output',str(args.output)],stdout=log,stderr=subprocess.STDOUT,check=True)
    provenance=dict(original_output=str(args.old_output),original_identity=old_ident,
                    justification='Only NPG stage batches changed; unaffected route records verified against previous engine.')
    reused=[]
    for algorithm in ('CE','LSTD_PI','DIRECT_PI'):
        for task in cfg['tasks']:
            filename=f"task-{task['id']:03d}.json"
            source=args.old_output/algorithm/'raw'/filename
            if source.exists():
                data=json.loads(source.read_text());assert data['identity']==old_ident and data['task']==task
                data['identity']=ident
                data['reuse_provenance']=dict(provenance,original_file=str(source),original_sha256=sha(source),
                                             previous_reuse_provenance=data.get('reuse_provenance'))
                save(args.output/algorithm/'raw'/filename,data)
                reused.append(dict(algorithm=algorithm,task=task['id'],kind='complete'))
            else:
                import numpy as np
                source=args.old_output/algorithm/'checkpoints'/filename.replace('.json','.npz')
                if not source.exists():continue
                with np.load(source,allow_pickle=False) as archive:
                    assert json.loads(str(archive['identity']))==old_ident
                    values={key:archive[key].copy() for key in archive.files}
                values['identity']=np.array(json.dumps(ident,sort_keys=True))
                target=args.output/algorithm/'checkpoints'/source.name;target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('wb') as stream:np.savez(stream,**values)
                save(target.with_suffix('.reuse.json'),dict(provenance,original_file=str(source),original_sha256=sha(source)))
                reused.append(dict(algorithm=algorithm,task=task['id'],kind='checkpoint'))
    source=args.old_output/'population_reference.json'
    reference=json.loads(source.read_text());assert reference['identity']==old_ident and reference['status']=='COMPLETE'
    reference['identity']=ident
    reference['reuse_provenance']=dict(provenance,justification='Population updates use identical step, horizon and 64 updates, independent of sample batches.',
                                     original_sha256=sha(source),previous_reuse_provenance=reference.get('reuse_provenance'))
    save(args.output/source.name,reference)
    save(args.output/'reuse_audit.json',dict(identity=ident,reused=reused,NPG_learning_results_reused=False,
        previous_constant_NPG_preserved_at=str(args.old_output/'NPG'),solver_rtol=cfg['solver_rtol']))
    save(status,dict(status='RUNNING',phase='learning',reused=reused,primary_NPG_schedule='growing'))
    result=subprocess.run([sys.executable,'-B',str(Path(__file__).parent/'fixed_value_pipeline.py'),
        '--manifest',str(args.manifest),'--output',str(args.output),'--prioritize-npg'])
    save(status,dict(status='COMPLETE' if result.returncode==0 else 'FAILED_PIPELINE',exit_code=result.returncode,reused=reused))
    raise SystemExit(result.returncode)


if __name__=='__main__':main()
