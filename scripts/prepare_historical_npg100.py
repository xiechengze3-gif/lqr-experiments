"""Freeze adaptive NPG on the two previously completed 100d benchmarks."""
import hashlib
import json
import shutil
from pathlib import Path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root=Path(__file__).resolve().parents[1]
    rank=Path('E:/ChatGPT/Results/LQR_experiments/npg-rank-complete-ea112fabeef4eb4a/npg-rank-ea112fabeef4eb4a')
    tail=Path('E:/ChatGPT/Results/LQR_experiments/approx-tail-preview-b16057241cf926bb-20261009-01/approx-tail-preview-b16057241cf926bb-20261009-01')
    engine=Path('E:/ChatGPT/Results/LQR_experiments/npg-budget-complete-e93b7ffa7fca793e/npg-budget-e93b7ffa7fca793e/engine/dense_scaling.py')
    dest=root/'local_runs'/'historical-npg100-adaptive'/'frozen'
    assert dest.resolve().is_relative_to(root.resolve())
    if dest.exists():raise FileExistsError(dest)
    rank_cfg=json.loads((rank/'source/manifest.json').read_text())
    tail_cfg=json.loads((tail/'source/approx_tail_suite.json').read_text())
    tasks=[]
    for path in sorted((rank/'raw').glob('task-*.json')):
        p=json.loads(path.read_text());t=p['task']
        if t['n']!=100:continue
        assert p['manifest_sha256']==sha(rank/'source/manifest.json')
        tasks.append(dict(benchmark='rank80',original_task=t,old_raw=str(path),old_sha256=sha(path),
                          schedule=rank_cfg['batch_schedule'],step_multiplier=rank_cfg['step_multiplier'],
                          horizon=rank_cfg['horizon'],burn=rank_cfg['burn'],sigma=rank_cfg['sigma']))
    for path in sorted((tail/'npg-524288/raw').glob('task-*.json')):
        p=json.loads(path.read_text());t=p['task']
        if t['n']!=100 or t['r']!=4:continue
        if not (t['tail_mode']=='exact' or (t['tail_mode']=='singular' and t['level'] in [.01,.03,.1])):continue
        assert p['manifest_sha256']==sha(tail/'source/approx_tail_suite.json')
        tasks.append(dict(benchmark='tail256',original_task=t,old_raw=str(path),old_sha256=sha(path),
                          schedule=tail_cfg['profiles']['npg-524288']['schedule'],
                          horizon=tail_cfg['horizon'],burn=tail_cfg['burn'],sigma=1.))
    assert len(tasks)==18
    for i,t in enumerate(tasks):t['id']=i
    originals={'dense_scaling.py':engine,'npg_batched_collector.py':root/'scripts/npg_batched_collector.py',
               'approx_tail_system.py':root/'scripts/approx_tail_system.py',
               'adaptive_rank.py':root/'scripts/adaptive_rank.py'}
    rank_p=json.loads((rank/'raw/task-007.json').read_text())
    tail_p=json.loads((tail/'npg-524288/raw/task-046.json').read_text())
    assert sha(engine)==rank_p['engine_sha256']==tail_p['engine_sha256']
    assert sha(originals['npg_batched_collector.py'])==tail_p['collector_sha256']
    assert sha(originals['approx_tail_system.py'])==tail_p['system_sha256']
    assert sha(root/'scripts/npg_rank_scaling.py')==rank_p['source_sha256']
    assert sha(root/'scripts/approx_tail_run.py')==tail_p['source_sha256']
    dest.mkdir(parents=True);vendor=dest/'vendor';vendor.mkdir()
    provenance=[]
    for name,source in originals.items():
        target=vendor/name;shutil.copy2(source,target)
        if name=='dense_scaling.py':
            original=target.read_text()
            revised=original.replace('if not os.environ.get("SLURM_JOB_ID"):',
                'if not (os.environ.get("SLURM_JOB_ID") or os.environ.get("LQR_COMPUTE_BACKEND") == "local"):')
            assert revised!=original
            target.write_text(revised,encoding='utf-8')
        provenance.append(dict(file=name,original_path=str(source),original_sha256=sha(source),
            local_sha256=sha(target),change='Local execution guard only' if name=='dense_scaling.py' else 'None'))
    for name in ('historical_npg100.py','historical_npg100_pipeline.py','historical_npg100_report.py'):
        shutil.copy2(root/'scripts'/name,dest/name)
    cfg=dict(tasks=tasks,methods=['raw','truncated','adaptive_1'],adaptive_multiplier=1.,
             adaptive_threshold='||Z_half1-Z_half2||op / 2; empirical, data-only',threads=2,
             replay_rtol=1e-8,replay_atol=1e-7,dispatch_chunk_updates=8,
             baseline_reuse='Validate original source hashes, initial metrics and first updates for each case; retain cross-platform provenance.',
             execution='Local; one worker, two numerical threads; continuous states and original exogenous seeds.')
    manifest=dest/'manifest.json';manifest.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
    (dest/'source_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    (root/'configs/historical_npg100_adaptive.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(frozen=str(dest),cases=len(tasks),new_adaptive_trajectories=len(tasks),historical_baseline_trajectories=2*len(tasks))))


if __name__=='__main__':main()
