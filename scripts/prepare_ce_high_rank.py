"""Package source and reused data only; numerical work stays on Grace."""
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RESULTS=Path('E:/ChatGPT/Results/LQR_experiments')


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    old=RESULTS/'cross-rank-complete-709f81b14811afb5/cross-rank-709f81b14811afb5/ce/raw'
    newer=RESULTS/'grace-aligned-b41df7278218861f/results/aligned-b41df7278218861f/tasks'
    reuse=[]
    for p in sorted(old.glob('task-*.json')):
        d=read(p);t=d['task']
        if t['n']==100 and t['r']==16 and t['tail']==0.:
            assert d['engine_sha256']==sha(ROOT/'dense_scaling.py')
            reuse.append(dict(source=str(p),sha256=sha(p),task=t,bundle_path=f"reused/r16-s{t['system_seed']}.json"))
    for p in sorted(newer.glob('*/result.json')):
        d=read(p);t=d['task']
        if t['algorithm']=='CE' and t['n']==100 and t['r']==32:
            assert d['identity']=='0f2d930bf4bf7a93e7c377666e5a22393826bca4b72dc1f91ddd50595f857dc8'
            task=dict(n=100,m=100,r=32,system_seed=t['system_seed'],trial_seed=t['sampling_seed'],
                      family='coupled_unstable',stabilizer='isotropic',tail=0.,tail_shape='energy')
            reuse.append(dict(source=str(p),sha256=sha(p),task=task,bundle_path=f"reused/r32-s{task['system_seed']}.json"))
    assert len(reuse)==4 and {(d['task']['r'],d['task']['system_seed']) for d in reuse}=={(16,0),(16,1),(32,0),(32,1)}
    tasks=[dict(n=100,m=100,r=rank,system_seed=seed,trial_seed=0,family='coupled_unstable',
                stabilizer='isotropic',tail=0.,tail_shape='energy') for rank in (64,100) for seed in (0,1)]
    files=['dense_scaling.py','scripts/ce_high_rank.py','scripts/prepare_ce_high_rank.py','slurm/ce_high_rank.sbatch']
    cfg=dict(title='100d CE high-rank absolute precision comparison',date='2026-10-15',n=100,
             ranks=[16,32,64,100],absolute_epsilon=.1,system_seeds=[0,1],sampling_seed=0,
             budgets=[512,2048,8192,32768,131072,524288,2097152],burn=512,sigma=1.,
             methods=['raw','truncated'],new_tasks=tasks,reused=reuse,
             generator='Historical coupled_unstable isotropic 981113 formulas; allow rank=n; skip empty tail division only',
             criterion='All two systems at a declared fixed prefix satisfy absolute J-Jstar <= .1; no cost-adaptive stopping',
             new_physical_transitions=4*(2097152+512),
             resources=dict(cores_per_task=1,threads=1,memory_GiB=2,wall_minutes=5,production_concurrency=2,
                            all_job_elements=6,maximum_reserved_SU=.5,campaign_SU_ceiling=1.,automatic_retries=0,
                            expected_SU_range=[.05,.15],performance_basis='Prior n100 full 2,097,152-prefix CE benchmark: 28.72 seconds, <224MiB peak; same-size collectors/solves'),
             scope='Two systems and the original coarse grid; A/F0/B vary with rank. Full rank must use this same extended generator, not the other nested family.',
             sources={f:sha(ROOT/f) for f in files})
    release=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()[:16];cfg['release']=release
    config=ROOT/'configs/ce_high_rank_20261015.json';config.write_text(json.dumps(cfg,indent=2)+'\n')
    bundle=ROOT/'analysis/ce-high-rank-20261015/release'/release;bundle.mkdir(parents=True,exist_ok=True)
    for f in files:
        dest=bundle/f;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/f,dest)
    for d in reuse:
        dest=bundle/d['bundle_path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(d['source'],dest)
        assert sha(dest)==d['sha256']
    shutil.copy2(config,bundle/'manifest.json')
    hashes=''.join(f'{sha(p)}  {p.relative_to(bundle).as_posix()}\n' for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='SHA256SUMS')
    (bundle/'SHA256SUMS').write_text(hashes,newline='\n')
    archive=ROOT/'packages'/f'ce-high-rank-{release}.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for p in sorted(bundle.rglob('*')):
            if p.is_file():tar.add(p,arcname=p.relative_to(bundle).as_posix())
    receipt=dict(state='PREPARED',release=release,archive=str(archive),archive_sha256=sha(archive),
                 reused_datasets=4,new_datasets=4,new_physical_transitions=cfg['new_physical_transitions'],
                 maximum_reserved_SU=.5,campaign_SU_ceiling=1.)
    (ROOT/'receipts/ce-high-rank-20261015.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':main()
