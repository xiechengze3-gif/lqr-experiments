"""Assemble findings, accounting and the final immutable metadata bundle."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tarfile
import time


def read(p):return json.loads(p.read_text())


def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def number(v):return '{:,}'.format(int(v)) if v is not None else 'not reached'


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);a=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    cfg=read(a.manifest);out=Path(cfg['output']);base=out.parent.parent;release=a.manifest.resolve().parents[1]
    os.environ['MPLCONFIGDIR']=str(Path(cfg['cache'])/'matplotlib')
    os.environ['NUMBA_CACHE_DIR']=str(Path(cfg['cache'])/'numba')
    os.environ['LQR_NUMBA_SITE']='/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages'
    for var in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[var]='1'
    Path(os.environ['MPLCONFIGDIR']).mkdir(parents=True,exist_ok=True)
    archives=base/'archives'/cfg['experiment'];assert not (archives/'final.json').exists()
    summary=read(out/'report-confirm/summary.json');raw_audit=read(out/'identification-audit/audit.json')
    assert summary['audit']['status']==raw_audit['status']=='PASS'
    assert len(summary['seeds'])==30 and summary['audit']['paired_tasks']==150
    assert summary['audit']['final_joint_OLS_recomputed']==150
    assert set(summary['seeds']).isdisjoint(cfg['pilot_seeds'])
    assert summary['audit']['full_rank_paired_budget_checks']==30*len(summary['budgets'])
    assert summary['audit']['unique_policies_reevaluated']==4050,'Retain the original complete independent audit'
    from ce500_execution_cost_audit import audit as execution_audit
    execution=execution_audit(cfg)
    for relative,digest in read(out/'preflight.json')['identity']['sources'].items():assert sha(release/relative)==digest
    shutil.copytree(release,out/'frozen/release',dirs_exist_ok=True)
    shutil.copytree(release/'docs',out/'documentation',dirs_exist_ok=True)
    old=base/'results/ce-matched-initial-gap-20261018/report-confirm/summary.json'
    old_summary=read(old);shutil.copyfile(old,out/'documentation/ce100_reference_summary.json')
    rank2=[];full=[];allrows=[]
    for rank in cfg['ranks']:
        for seed in cfg['confirm_seeds']:
            raw=read(out/'raw'/f'ce-r{rank:03d}-s{seed:04d}.json');allrows+=raw['records']
            if rank in (2,cfg['n']):
                selected=[q for q in raw['records'] if q['ols_samples']==131072]
                (rank2 if rank==2 else full).extend(selected)
    def med(rows,method,key):
        values=[q[key] if q[key] is not None else math.inf for q in rows if q['method']==method]
        v=statistics.median(values);return v if math.isfinite(v) else None
    models=dict(transitions=131328,seeds=30,rank=2,
        dense_B_error_fro2_median=med(rank2,'dense','B_error_fro2'),
        truncated_B_error_fro2_median=med(rank2,'truncated','B_error_fro2'),
        dense_gap_median=med(rank2,'dense','gap'),truncated_gap_median=med(rank2,'truncated','gap'),
        full_rank_dense_gap_median=med(full,'dense','gap'))
    models['B_error_improvement']=models['dense_B_error_fro2_median']/models['truncated_B_error_fro2_median']
    models['within_rank_gap_improvement']=models['dense_gap_median']/models['truncated_gap_median']
    models['full_dense_over_low_truncated_gap']=models['full_rank_dense_gap_median']/models['truncated_gap_median']
    write(out/'report-confirm/paired_model_and_gap_comparison.json',models)
    pilot=read(out/'pilot_submission.json');formal=read(out/'formal_submission.json')
    ids=[read(out/'preflight.json')['slurm_job_id'],pilot['pilot_array'],pilot['pilot_report'],
         read(out/'common_bundle_submission.json')['common_bundle_job']]+list(formal['arrays_by_rank'].values())
    ids += [formal['formal_report'],formal['identification_audit']]+[q['job_id'] for q in formal['bundle_jobs']]
    ids += formal.get('recovery_jobs',[])+formal.get('retired_auxiliary_jobs',[])
    ledger=out/'accounting/science_and_prior_archives.psv';ledger.parent.mkdir(exist_ok=True)
    for attempt in range(8):
        accounting=subprocess.check_output(['sacct','-j',','.join(ids),'--noheader','--parsable2',
            '--format=JobIDRaw,JobID,State,ExitCode,ElapsedRaw,AllocCPUS,ReqMem,AllocTRES,TotalCPU,NNodes,TimelimitRaw,MaxRSS'],text=True)
        if not any(any(state in line for state in ('RUNNING','PENDING','COMPLETING')) for line in accounting.splitlines()):break
        time.sleep(5)
    ledger.write_text(accounting)
    subprocess.run([sys.executable,'-B',str(release/'scripts/account_rank_sweep100.py'),'--input',str(ledger),
        '--output',str(out/'accounting/occupancy_before_final_archive.json'),'--cap','60','--cap-unit','allocated_core_hours'],check=True)
    occupancy=read(out/'accounting/occupancy_before_final_archive.json')
    recovery=read(out/'recovery_plan.json')
    cases=[recovery]+recovery.get('additional_cases',[])
    expected_jobs=186+formal.get('recovery_attempts',len(formal.get('recovery_jobs',[])))+len(formal.get('retired_auxiliary_jobs',[]))
    assert {q['job_id_raw'] for q in occupancy['failed_jobs']}=={c['failed_job_id'] for c in cases},occupancy
    assert all(q['state']=='TIMEOUT' for q in occupancy['failed_jobs']) and occupancy['job_records']==expected_jobs,occupancy
    subprocess.run([sys.executable,'-B',str(release/'scripts/collect_matched_gap_settlement.py'),
        '--account',cfg['resources']['account'],'--start','2026-10-19','--end','2026-10-21',
        '--accounting',str(ledger),'--output',str(out/'accounting/settlement_before_final_archive')],check=True)
    requirements=summary['requirements']
    def req(rank,method,target):return next(q for q in requirements if q['rank']==rank and q['method']==method and q['relative_target']==target)
    def contrast(rank,target):return next(q for q in summary['low_rank_vs_full_rank'] if q['rank']==rank and q['relative_target']==target)
    lines=['# CE500 固定初始 optimality gap 实测结果','',
        '已完成5-seed pilot和每个rank30个独立正式种子（200–229）。n=m=500，rank=2/8/32/64/500，Q=R=W=I，初始gap=1；relative target0.1/0.05亦为共同absolute target。',
        '', '| rank | Dense N(0.1) | Truncated N(0.1) | Dense N(0.05) | Truncated N(0.05) |',
        '|---|---:|---:|---:|---:|']
    for rank in cfg['ranks']:
        vals=[req(rank,m,t)['N_hat_90'] for t in cfg['relative_targets'] for m in ('dense','truncated')]
        lines.append('| {} | {} |'.format(rank,' | '.join(number(v) for v in vals)))
    lines+=['','Nhat为已测预算中至少27/30输出在真实系统稳定且达标的最小primitive transitions，含256次burn-in。全部失败保留。CSV另存相邻较小预算、成功率及Wilson95%区间、配对bootstrap区间。网格点估计不等于连续预算的精确门槛；30/30的Wilson区间下界仍为88.65%，不能称95%置信保证总体成功率至少90%。','',
        '| target | full500 dense / rank2 truncated 样本节省倍数 | rank2命中数及Wilson95% | full500命中数及Wilson95% |',
        '|---|---:|---|---|']
    for target in cfg['relative_targets']:
        c=contrast(2,target);low,high=req(2,'truncated',target),req(cfg['n'],'dense',target)
        def success(q):return '{}/30 [{:.2%}, {:.2%}]'.format(q['threshold_or_endpoint_successes'],q['success_ci95_low'],q['success_ci95_high'])
        factor=c['sample_saving_factor_full_over_low']
        lines.append('| {} | {} | {} | {} |'.format(target,'{:.3f}'.format(factor) if factor else 'censored',success(low),success(high)))
    unstable=sum(q.get('failure')=='controller_instability' for q in allrows)
    numerical=sum(q.get('failure')=='riccati_failure' for q in allrows)
    lines+=['','正式全预算共{}个方法输出，不稳定{}个，Riccati失败{}个。同一种子多个预算并非独立试验；各预算不稳定率的区间见success_by_budget.csv。'.format(len(allrows),unstable,numerical),
        '', '识别流程为真实连续trajectory的[x_t,u_t]→x_(t+1)联合OLS，保留同一个Ahat，仅截断Bhat后Riccati。没有ridge、白化或真实子空间。rank500恒等截断共{}组预算检查全部一致。'.format(summary['audit']['full_rank_paired_budget_checks']),
        '', '独立审计用8192步新trajectory/每rank验证时间对齐、实际控制输入、直接lstsq与充分统计量OLS、已知噪声扣除后的无噪声[A,B]恢复；另对正式seed200的最终策略重算Riccati。审计PASS，详见identification-audit/audit.json。只能说这些检查未发现差异，不能把有限检查说成排除所有bug。',
        '', '同为131,328 transitions时，rank2模型B误差Frobenius平方中位数dense={:.8g}、truncated={:.8g}（{:.2f}倍）；gap中位数{:.8g}、{:.8g}（{:.2f}倍）；full500 dense gap={:.8g}，为rank2 truncated的{:.2f}倍。主样本复杂度结论来自共同最终gap及成功率，而非把模型误差比值换算成样本比值。'.format(models['dense_B_error_fro2_median'],models['truncated_B_error_fro2_median'],models['B_error_improvement'],models['dense_gap_median'],models['truncated_gap_median'],models['within_rank_gap_improvement'],models['full_rank_dense_gap_median'],models['full_dense_over_low_truncated_gap']),
        '', '100维对照的原始正式summary一并保存于documentation/ce100_reference_summary.json；比较各自ambient dimension内的full+dense / rank2+trunc样本需求比值：']
    for target in cfg['relative_targets']:
        old_c=next(q for q in old_summary['low_rank_vs_full_rank'] if q['rank']==2 and q['relative_target']==target)
        new_c=contrast(2,target)
        lines.append('- target{}：d100={:.3f}倍，d500={}倍。'.format(target,old_c['sample_saving_factor_full_over_low'],new_c['sample_saving_factor_full_over_low']))
    physical=read(out/'preflight.json')['diagnostic_primitive_transitions']+read(out/'report-pilot/audit.json')['physical_transitions']+summary['audit']['physical_transitions']+raw_audit['diagnostic_primitive_transitions']
    lines+=['','这是每个维度一个共同随机系统实例上的empirical observation。匹配初始gap仍不匹配控制能力、探索状态分布或控制误差的方向权重，跨rank/维度差异不能直接归因于估计器。Dense跨rank是否单调须按表中实际数值判断，不预设低rank一定更难。',
        '', '运行与保存：全部学习、数值审计和科学绘图在Grace计算节点完成，1CPU单线程；总实际SU上限60，冻结配置、所有策略/OLS/状态与RNG断点、原始结果和失败记录均保存。共享OLS物理采样仅计一次，各算法分别计同一前缀预算。总已提交有效数据transition={}（含pilot及独立诊断），实际执行总数在[{}, {}]，不能把丢失工作当作精确0。归档分组下载到E盘并逐文件验证；成本最终结算另存同级ce500-matched-gap-20261019-bundles/final-accounting，避免最后归档作业结算延迟使冻结数据发生变化。'.format(number(physical),number(execution['total_primitive_transitions_lower']),number(execution['total_primitive_transitions_upper'])),
        '', '资源中断：rank32 seed216（20205483,c294）及rank8 seeds227/228（20205931/20205934,c136）超过21分钟时限，3次TIMEOUT及全部费用保留。三者最后成功断点均为786,432个OLS样本（含burn共786,688 transitions），两个方法在此之前均已达到0.05；每条仅从原RNG/状态/Gram断点续跑最后262,144样本。第一条续跑20205945实际129秒，另两条使用20206044数组，每任务最多一次续跑。三者未提交工作总量只能界定为0–786,432 transitions，没有伪造精确计数。Slurm自动取消的未启动归档均按相同内容恢复，完整审计范围和旧取消记录保留。',
        '', '执行成本复核：在三次丢失工作均为0和均为262,144两种端点下，按各物理预算时可用的最后一份已提交策略重新计数；20项Nhat90与所有种子逐预算成功事件完全相同，所以Wilson及配对bootstrap的Nhat区间也不变。主gap图按最大丢失工作的可用策略绘制，橙色为三条运行各自丢失量端点全部8种组合的中位数范围，不预设gap单调；原OLS数据前缀图另存*_OLS_prefix。详见report-confirm/execution_cost_audit.json及executed_budget_gaps.csv。',
        '', '环境问题：threadpoolctl检测一个BLAS版本时打印非致命callback AttributeError。环境显式限制线程数为1，识别到的SciPy OpenBLAS报告1线程；计算及独立数值复核通过。保留原始日志。最终费用要区分Slurm分配核时与AMS显示的逐作业舍入SU，不将待结算记录计为零。',
        '', '归档首次提交因引用已从Slurm控制器清理的完成作业而报Job dependency problem，未生成作业、不计计算费用；按sacct核实完成状态后，从依赖中移除已完成作业，再提交归档。正式学习不受影响，失败提交元数据保留。',
        '', '图表：report-confirm/sample_complexity_vs_rank、success_probability_vs_budget、absolute_relative_gap_convergence、same_budget_gap_improvement（PNG及SVG）。']
    (out/'documentation/CE500_FINDINGS_ZH.md').write_text('\n'.join(lines)+'\n')
    write(out/'execution_provenance.json',dict(status='PASS',formal_tasks=150,pilot_tasks=25,
        total_scientific_and_prior_archive_jobs=expected_jobs,final_archive_job_id=os.environ['SLURM_JOB_ID'],
        committed_primitive_transitions=physical,actual_primitive_transitions_interval=[execution['total_primitive_transitions_lower'],execution['total_primitive_transitions_upper']],
        execution_cost_audit='report-confirm/execution_cost_audit.json',
        known_timeout_jobs=[c['failed_job_id'] for c in cases],recovery_jobs=formal.get('recovery_jobs',[]),
        retired_zero_runtime_auxiliary_jobs=formal.get('retired_auxiliary_jobs',[]),formal_plan_sha256=sha(out/'formal_plan.json'),
        ce100_reference_summary_sha256=sha(old),all_pre_final_jobs_terminal=True,
        final_accounting_location='E:/ChatGPT/Results/LQR_experiments/ce500-matched-gap-20261019-bundles/final-accounting',
        source_sha256=sha(Path(__file__))))
    # Final bundle includes all uncovered or changed files, including failed-run remnants.
    covered={}
    for label in ['common']+['formal-%02d'%i for i in range(6)]:covered.update(read(archives/(label+'.json'))['files_sha256'])
    files={str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='artifact_sha256.json'}
    write(out/'artifact_sha256.json',files)
    chosen=[out/relative for relative,digest in files.items() if covered.get(relative)!=digest]+[out/'artifact_sha256.json']
    file_hashes={str(f.relative_to(out)):sha(f) for f in chosen}
    archive=archives/'final.tar.gz';temporary=archives/'final.tmp.tar.gz'
    with tarfile.open(temporary,'w:gz',compresslevel=1) as bundle:
        for source in sorted(chosen):bundle.add(source,arcname=cfg['experiment']+'/'+str(source.relative_to(out)),recursive=False)
    os.replace(temporary,archive)
    result=dict(status='complete',kind='final',group=0,archive=str(archive),archive_sha256=sha(archive),
        archive_bytes=archive.stat().st_size,files_sha256=file_hashes,global_scientific_files=len(files),slurm_job_id=os.environ['SLURM_JOB_ID'])
    write(archives/'final.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='files_sha256'}))


if __name__=='__main__':main()
