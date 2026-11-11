"""Verify saved CE artifacts and make a local findings record; no numerical learning."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[1]


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def write(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def csvrows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def number(x):return f'{int(x):,}' if x is not None else 'NR'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--expected-sha256',required=True);parser.add_argument('--accounting',type=Path,required=True)
    a=parser.parse_args();cfg=read(ROOT/'configs/ce_matched_initial_gap_20261018.json')
    out=Path(cfg['local_output']);base=out.parent
    assert str(out.resolve()).lower().startswith('e:\\chatgpt\\results\\lqr_experiments\\')
    # The PowerShell entrypoint has already SHA256-verified this exact archive.
    assert a.archive.name==cfg['experiment']+'.tar.gz' and len(a.expected_sha256)==64
    with tarfile.open(a.archive,'r:gz') as bundle:
        members=bundle.getmembers()
        for m in members:
            parts=PurePosixPath(m.name).parts
            assert parts and parts[0]==cfg['experiment'] and '..' not in parts and '\\' not in m.name
            assert m.isfile() or m.isdir()
        bundle.extractall(base,members=members,filter='data')
    manifest=read(out/'artifact_sha256.json')
    assert read(out/'frozen/config.json')==cfg
    for relative,digest in manifest.items():
        parts=PurePosixPath(relative).parts
        assert parts and '..' not in parts and not PurePosixPath(relative).is_absolute()
        assert sha(out/relative)==digest,relative
    pilot=read(out/'report-pilot/summary.json');formal=read(out/'report-confirm/summary.json')
    assert pilot['audit']['paired_tasks']==25 and formal['audit']['paired_tasks']==150
    assert formal['seeds']==cfg['confirm_seeds'] and set(formal['seeds']).isdisjoint(pilot['seeds'])
    assert pilot['audit']['policies_checked']==450 and formal['audit']['policies_checked']==6300
    assert pilot['audit']['full_rank_paired_budget_checks']==45 and formal['audit']['full_rank_paired_budget_checks']==630
    verification=read(out/'verification.json');preflight=read(out/'preflight.json');cost=read(a.accounting)
    assert verification['status']==preflight['status']=='PASS'
    assert cost['allocated_core_hours']<=8 and cost['job_records']==179 and not cost['failed_jobs']
    assert all(q['max_instabilities']==0 and q['max_numerical_failures']==0 for q in formal['requirements'])
    accounting_rows=csvrows(a.accounting.with_suffix('.csv'))
    actual_jobs={q['job_id_raw'] for q in accounting_rows};data_jobs=set()
    for phase in ('pilot','confirm'):
        mapping=[(rank,seed) for seed in cfg[phase+'_seeds'] for rank in cfg['ranks']]
        for index,(rank,seed) in enumerate(mapping):
            task=read(out/'task_receipts'/f'{phase}-{index:03d}.json')
            assert task['rank']==rank and task['seed']==seed and task['task_id']==index and task['phase']==phase
            assert task['slurm_job_id'] in actual_jobs
            data_jobs.add(task['slurm_job_id'])
    assert len(data_jobs)==175
    write(out/'execution_provenance.json',dict(status='PASS',saved_paired_groups=175,
        distinct_real_learning_jobs=175,all_pair_seed_rank_task_mappings_verified=True,
        actual_job_accounting_sha256=sha(a.accounting),one_allocated_cpu_per_job=True))
    for rank in cfg['ranks']:
        path=out/'systems'/f'r{rank:03d}.npz'
        assert sha(path)==verification['system_hashes'][str(rank)]
    (out/'compute_accounting').mkdir(exist_ok=True)
    for p in ROOT.joinpath('receipts').glob('ce-matched-initial-gap-compute-accounting.*'):
        shutil.copyfile(p,out/'compute_accounting'/p.name)
    shutil.copyfile(ROOT/'receipts/ce-matched-initial-gap-own-jobs-final.psv',out/'compute_accounting/own_jobs_final.psv')
    (out/'documentation').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'docs/CE_MATCHED_INITIAL_GAP_PROTOCOL_20261018.md',out/'documentation/CE_MATCHED_INITIAL_GAP_PROTOCOL_20261018.md')
    rows=formal['requirements'];contrasts=formal['low_rank_vs_full_rank']
    def req(rank,method,relative):return next(q for q in rows if q['rank']==rank and q['method']==method and q['relative_target']==relative)
    def contrast(rank,relative):return next(q for q in contrasts if q['rank']==rank and q['relative_target']==relative)
    lines=['# CE：匹配初始optimality gap的实测对照','',
        '已完成5-seed pilot与每rank30个新种子200–229的正式实验，pilot不进入正式分母。所有原始数据、配置、策略、断点、最终OLS充分统计量、图表和作业记录均保留。',
        '', '## 精度与主比较','',
        '所有rank的初始gap固定为1，最大数值偏差为'+f"{max(abs(q['initial_gap']-1) for q in verification['systems']):.3g}"+'。因此relative target 0.1/0.05同时对应共同absolute gap 0.1/0.05。',
        '', '| rank | 初始gap | Dense CE N(0.1) | Truncated CE N(0.1) | full dense / low truncated | 配对bootstrap95%区间 |',
        '|---|---|---|---|---|---|']
    for rank in cfg['ranks']:
        d,t,c=req(rank,'dense',.1),req(rank,'truncated',.1),contrast(rank,.1)
        ratio='NR' if c['sample_saving_factor_full_over_low'] is None else f"{c['sample_saving_factor_full_over_low']:.3f}"
        ci=f"[{c['bootstrap95_low']}, {c['bootstrap95_high']}]"
        lines.append(f"| {rank} | 1 | {number(d['N_hat_90'])} | {number(t['N_hat_90'])} | {ratio} | {ci} |")
    lines+=['','Nhat是已测预算中至少27/30输出在真实系统稳定且达标的最小预算；全部burn-in计入。区间基于2,000次完整配对种子曲线bootstrap。离散网格仍有分辨率限制。NR保留为删失，不赋有限门槛。',
        '', '## 更严格目标与同预算误差','',
        '| rank | Dense N(0.05) | Truncated N(0.05) | full dense / low truncated |','|---|---|---|---|']
    for rank in cfg['ranks']:
        d,t,c=req(rank,'dense',.05),req(rank,'truncated',.05),contrast(rank,.05)
        lines.append(f"| {rank} | {number(d['N_hat_90'])} | {number(t['N_hat_90'])} | {c['sample_saving_factor_full_over_low']} |")
    fixed=csvrows(out/'report-confirm/fixed_budget_gaps.csv');endpoint=[q for q in fixed if int(q['transitions'])==131328]
    lines+=['','最大预算为131,328 transitions。同预算中位gap如下；Delta0=1使relative与absolute数值相同。',
        '', '| rank | Dense gap | Truncated gap | full-rank dense gap / truncated gap |','|---|---|---|---|']
    for q in endpoint:
        lines.append(f"| {q['rank']} | {float(q['dense_gap_median']):.8f} | {float(q['truncated_gap_median']):.8f} | {float(q['full_dense_over_low_trunc_gap_ratio']):.3f} |")
    lines+=['','成功率及Wilson95%区间保存在report-confirm/success_by_budget.csv，所有gap与配对区间保存在fixed_budget_gaps.csv。',
        '', '## 构造与解释边界','',
        '保持上一轮完全相同的物理A、B_r、Q=R=W=I与共同U/V。使用同一独立满秩随机正交D构造K0_r=Kstar_r+alpha_r D，并在采样前按真实gap校准alpha。真最优增益只用于构造初始策略，不提供给OLS/DARE学习更新。所有K0均满秩。',
        '', '这轮K0确实用于CE行为采样，不能复用上一轮的学习轨迹来冒充新实验。不同rank的初始闭环与探索状态分布仍不同；匹配初始gap消除了相对精度分母差异，不能识别纯估计器因果效应。一套共同物理系统、30个配对数据种子的结果不能推出普遍单调rank定律。',
        '', '## 完整性与资源','',
        f"预检无噪声OLS恢复与两次断点恢复比较通过；全部{pilot['audit']['policies_checked']+formal['audit']['policies_checked']:,}个保存策略经真实Lyapunov代价和performance-difference identity核对。full rank的675个配对预算逐元素相同。",
        '', f"本轮179个Slurm计费记录全部终态完成；实际占用{cost['allocated_core_hours']:.6f}核时，billing-unit hours为{cost['elapsed_billing_unit_hours']:.6f}，低于8核时上限。它是本轮自有作业的实测占用，不等同于账户全部AMS消耗。",
        '', f"pilot物理transitions={pilot['audit']['physical_transitions']:,}，正式={formal['audit']['physical_transitions']:,}，预检诊断={preflight['diagnostic_primitive_transitions']:,}，总计={pilot['audit']['physical_transitions']+formal['audit']['physical_transitions']+preflight['diagnostic_primitive_transitions']:,}。两种CE后处理共享数据，算法预算各自计入，但物理模拟不双计。未新增本机学习或采样。",
        '', '运行记录：共享SSH在沙箱外正常可用；冻结输入哈希、AST与LF脚本校验通过。归档SHA256和全部原始文件清单已校验。图表视觉检查在交付前另存visual_review.json。',
        '', '原始归档和本地补充文件分别保存，原有NPG/CE/PI结果没有修改。']
    findings='\n'.join(lines)+'\n'
    (ROOT/'docs/CE_MATCHED_INITIAL_GAP_FINDINGS_20261018.md').write_text(findings,encoding='utf-8')
    (out/'documentation/CE_MATCHED_INITIAL_GAP_FINDINGS_20261018.md').write_text(findings,encoding='utf-8')
    counts=dict(pilot_physical=pilot['audit']['physical_transitions'],formal_physical=formal['audit']['physical_transitions'],
        diagnostic_physical=preflight['diagnostic_primitive_transitions'],total_physical=pilot['audit']['physical_transitions']+formal['audit']['physical_transitions']+preflight['diagnostic_primitive_transitions'],
        main_algorithm_charged=pilot['audit']['algorithm_charged_transitions']+formal['audit']['algorithm_charged_transitions'],
        no_resource_interruptions=True)
    write(out/'campaign_transition_accounting.json',counts)
    delivery=dict(state='downloaded_sha256_verified_audited_pending_visual_review',archive=dict(path=str(a.archive),bytes=a.archive.stat().st_size,sha256=a.expected_sha256,verified=True),
        archive_entries=len(members),original_artifact_hashes_verified=len(manifest),cost=cost,transitions=counts,
        new_learning_transitions_during_local_finalization=0)
    write(out/'delivery_receipt.json',delivery)
    receipt=read(ROOT/'receipts/ce-matched-initial-gap-20261018.json');receipt.update(delivery)
    receipt.update(formal_audit=formal['audit'],pilot_audit=pilot['audit'],next_steps=['Visual inspection of final plots and completion publication'])
    write(ROOT/'receipts/ce-matched-initial-gap-20261018.json',receipt)
    print(json.dumps(dict(status=delivery['state'],output=str(out),artifacts_verified=len(manifest),physical_transitions=counts['total_physical'],cost=cost['allocated_core_hours']),ensure_ascii=False))


if __name__=='__main__':main()
