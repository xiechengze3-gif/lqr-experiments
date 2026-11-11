"""Freeze tonight's bounded experiment and the saved evidence inputs."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]
NAME='project2-overnight-20261020'


def main():
    package=ROOT/'packages'/NAME
    assert not package.exists(), 'Frozen package already exists; inspect before changing'
    out='/scratch/user/changze/lqr_experiments/results/'+NAME
    tasks=[]
    for seed in (2801,2802):
        for count in (32768,131072,524288):
            for method in ('dense','known_rank','adaptive'):
                tasks.append(dict(id=len(tasks),tag='pilot',n=50,m=50,r=4,seed=seed,
                    trial=0,N=count,H=16,burn=512,updates=6,method=method))
    cfg=dict(name=NAME,output=out,SU_cap=100,account='132685389143',
             pilot_tasks=tasks,actor_tasks=[],mechanism_tasks=[],
             policy='Independent pilot freezes common full-greedy PI budgets. Reuse completed evidence first.')
    cfgpath=ROOT/'configs/project2_overnight_20261020.json'
    cfgpath.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
    files=['scripts/project2_overnight.py','scripts/npg_batched_collector.py',
           'scripts/direct_stein_final.py','dense_scaling.py','slurm/project2_overnight.sbatch',
           'configs/project2_overnight_20261020.json','docs/PROJECT2_OVERNIGHT_PROTOCOL_20261020.md']
    for rel in files:
        p=ROOT/rel
        if p.suffix=='.py': ast.parse(p.read_text(encoding='utf-8'))
        dest=package/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        data=p.read_bytes()
        dest.write_bytes(data.replace(b'\r\n',b'\n') if p.suffix=='.sbatch' else data)
    previous=Path('E:/ChatGPT/Results/LQR_experiments/final-round-20261014')
    inputs=[]
    for folder in ('scaling','pilot-fixed'):
        for source in sorted((previous/folder).glob('*')):
            if source.suffix not in ('.npz','.json') or not source.name.startswith('n'):continue
            dest=package/'inputs/estimates'/source.name
            if dest.exists():assert dest.read_bytes()==source.read_bytes()
            else:
                dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
                inputs.append(str(dest.relative_to(package)).replace('\\','/'))
    for folder,target in [('core','policies'),('core/systems','systems')]:
        for source in sorted((previous/folder).glob('*')):
            if source.suffix not in ('.npz','.json') or not source.name.startswith('n'):continue
            dest=package/'inputs'/target/source.name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,dest);inputs.append(str(dest.relative_to(package)).replace('\\','/'))
    allfiles=files+inputs
    hashes={rel:hashlib.sha256((package/rel).read_bytes()).hexdigest() for rel in allfiles}
    (package/'SHA256SUMS').write_text(''.join(d+'  '+rel+'\n' for rel,d in hashes.items()),encoding='utf-8',newline='\n')
    archive=ROOT/'packages'/(NAME+'.tar.gz')
    with tarfile.open(archive,'w:gz') as bundle:bundle.add(package,arcname=NAME)
    receipt=dict(package=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        bytes=archive.stat().st_size,files=len(hashes),pilot_tasks=len(tasks),SU_cap=100,
        output=out,free_E_bytes=shutil.disk_usage(ROOT).free)
    (ROOT/'receipts'/(NAME+'-package.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
