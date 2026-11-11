"""Build Chinese delivery notes exclusively from audited saved results."""
import argparse
import hashlib
import json
from pathlib import Path


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def number(v):return 'not reached' if v is None else format(int(v),',')


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--review',type=Path,required=True);p.add_argument('--document',type=Path,required=True)
    a=p.parse_args();root=a.root;review=a.review
    joined=read(root/'joined-report/all_algorithms_summary.json');rows=joined['requirements']
    formal=read(root/'report-confirm/summary.json');pilot=read(root/'report-pilot/summary.json')
    cost=read(review/'compute_accounting.json');execution=read(review/'transition_and_execution_audit.json')
    peak=cost['maximum_recorded_step_RSS_bytes']
    peak_text=f'{peak/1024**3:.4f}GiB' if peak is not None else '计数不可用'
    archive=read(root/'local_archive_verification.json');settled=read(review/'settlement/own_settlement_summary.json')
    billing=read(review/'billing_reconciliation.json')
    visual=read(review/'visual_review.json');ratios=read(review/'reviewed_low_truncated_vs_full_dense.json')
    assert len(rows)==60 and all(q['seeds']==30 and q['initial_gap']==1 for q in rows)
    assert joined['status']==formal['status']==pilot['status']=='complete'
    assert execution['status']==archive['status']==visual['status']=='PASS'
    assert all(v['status']=='PASS' for v in formal['audits'].values())
    verification=read(root/'system_verification.json');assert verification['status']=='PASS'
    certificate=max(q['certificate_max_error'] for q in verification['checks'])
    def cell(alg,r,m,eps):
        return next(q for q in rows if (q['algorithm'],q['rank'],q['method'],q['relative_target'])==(alg,r,m,eps))
    text=['# 初始 optimality gap=1：CE / Stein NPG / 原坐标 LSTD PI 实测记录','',
        '正式实验已完成。NPG和PI各有5个pilot seeds及30个新正式seeds（300–329），每个seed覆盖rank2/8/32/64/100；pilot不进入正式统计。CE复用已完成的30个正式seeds（200–229），新算法加载与CE逐字节相同的五份系统及初始策略文件。','',
        '所有初始gap均为1（最大偏差2.13e-13）。relative gap定义为 (J(K)-Jstar)/(J(K0)-Jstar)，所以target0.1/0.05同时是absolute gap0.1/0.05，分别要求消除90%/95%的初始gap。它不除以Jstar。','',
        f'物理系统保持n=m=100、Q=R=W=I、b=1，共同A/U/V和嵌套B_rank不变。按K0_r=Kstar_r+alpha_r D构造初始策略，共用一个独立满秩随机正交D，alpha只用于在采样前校准gap。各K0均满秩100；真实最优策略及子空间仅用于私有系统构造、oracle和事后评价，不进入学习更新。初始稳定性、rank及Lyapunov证书均通过，最大证书残差{certificate:.4g}。这轮K0、J0和初始闭环随rank变化。','',
        '表中N是冻结采样协议下，第一个至少27/30成功的已测累计primitive-transition预算。NPG/PI要求整个学习路径稳定；CE要求该预算输出在真实系统上稳定。所有burn-in和Stein priming blocks均计入。此处没有搜索所有可能的批次、步长和更新次数来求全局最优样本量。','',
        '**主要对照：rank2+truncation 与 rank100+dense。**','',
        '| 算法 | relative=absolute target | rank2 truncated N | full-rank dense N | full/low 样本比 |','|---|---:|---:|---:|---:|']
    for alg in ('CE','NPG','PI'):
        for eps in (.1,.05):
            low=cell(alg,2,'truncated',eps)['N_hat_90'];full=cell(alg,100,'dense',eps)['N_hat_90']
            ratio=f'{full/low:.5f}' if full is not None and low is not None else '删失；不估计有限比值'
            text.append(f'| {alg} | {eps:g} | {number(low)} | {number(full)} | {ratio} |')
    text+=['','target0.05下，full-rank dense NPG在245,902,512、PI在3,474,432的最大预算仍为0/30成功，精度失败率100%，Wilson95%区间[88.65%,100%]；没有给它们编造有限N。rank2截断NPG/PI达到两个目标的首次预算均为30/30成功，成功率Wilson95%区间[88.65%,100%]。CE/rank2截断首次预算为29/30，区间[83.33%,99.41%]。经验成功率达90%不等同于总体成功率的95%置信下界已达90%。','']
    for eps in (.1,.05):
        text += [f'**全rank样本需求，target={eps:g}。**','',
            '| rank | CE dense | CE trunc | NPG dense | NPG trunc | PI dense | PI trunc |',
            '|---:|---:|---:|---:|---:|---:|---:|']
        for rank in (2,8,32,64,100):
            values=[number(cell(alg,rank,m,eps)['N_hat_90']) for alg in ('CE','NPG','PI') for m in ('dense','truncated')]
            text.append('| '+str(rank)+' | '+' | '.join(values)+' |')
        text.append('')
    text += ['CE最大预算131,328；NPG最大预算245,902,512；PI最大预算3,474,432。全部逐预算成功率、Wilson区间、2000次种子bootstrap的N区间和不稳定率保存在原始报告CSV及joined-report/all_algorithms_sample_complexity.csv。NPG/rank2/target0.05的N区间是78,127,752至94,905,228；CE/rank2/target0.05为5,376至6,400。离散grid上的退化区间不代表网格内最小样本数已经精确识别。','',
        '**同预算的最终gap。每个算法使用其自身的共同最大预算；表内是30个正式seed中位数。**','',
        '| 算法 | rank | Dense gap | Truncated gap |','|---|---:|---:|---:|']
    for alg in ('CE','NPG','PI'):
        for rank in (2,8,32,64,100):
            d=cell(alg,rank,'dense',.1);t=cell(alg,rank,'truncated',.1)
            text.append(f'| {alg} | {rank} | {d["endpoint_gap_median"]:.9f} | {t["endpoint_gap_median"]:.9f} |')
    text += ['','三个算法在rank2均观察到“低rank+截断比full rank+dense省样本”。NPG在rank8也有优势，但rank32/64截断仍未达target0.1。CE在rank32/64仍比full rank需要更多样本。PI在target0.1下，rank2/8节省10.5866倍、rank32节省2.5231倍、rank64与full rank同一预算档达标。因而不能把结果概括成普遍单调的rank定律。在各自冻结协议下，CE的绝对样本需求仍最低。','',
        '**优化与实验公平性。**','',
        '所有rank使用统一NPG eta=.05、H=4、sigma=2、burn=256及44次更新。blocks分别为16384/65536/262144/1048576各8次，再4194304共12次；预算逐档增长，正式阶段不按rank或结果单独调参。PI使用完整原坐标20100系数LSTD critic，无样本白化、ridge或critic降维；统一rtol=1e-6、同样的两次Krylov求解尝试和四档batch[65536,262144,1048576,2097152]，每次burn=256。截断只作用于Stein Zhat或PI actor的联合左块[G,C]。','',
        '| rank | exact NPG至0.1 | exact NPG至0.05 | exact PI至两个目标 |','|---:|---:|---:|---:|']
    for rank in (2,8,32,64,100):
        d=cell('NPG',rank,'dense',.1);t=cell('NPG',rank,'dense',.05)
        text.append(f'| {rank} | {d["oracle_iterations"]} | {t["oracle_iterations"]} | 1 |')
    text += ['','finite-H population oracle（无采样噪声）与exact NPG的达标迭代数相同，44次上限对全部rank足够。匹配gap没有匹配曲率：rank2 exact NPG至0.05需29步，full rank需14步；rank2初始gap约94.94%位于没有控制作用的输入增益方向。因此，本轮排除了所测无噪声轨迹上统一迭代上限不足，仍不能把跨rank样本趋势纯归因于估计器。不同rank同时改变控制能力、初始闭环和探索状态分布。','',
        '同rank内，CE的dense/truncated共享完整原始OLS估计；NPG/PI在策略及状态相同时共享实际估计，分叉后使用配对外生随机流。跨rank随机流配对，真实子空间不提供给学习器。rank100跳过恒等SVD，配对策略逐元素一致。只在算法内做配对；不同算法没有宣称共享相同trajectory。','',
        '**CE识别流程与收益诊断。**','',
        '实际行为trajectory为u=-K0 x+e、xnext=A x+B u+w。记录Z=[x;u]与Xnext，联合普通最小二乘得到[Ahat,Bhat]=Xnext Z^T (Z Z^T)^(-1)，实现使用Cholesky求解；无ridge和样本白化。Truncated CE保留同一个Ahat，仅对Bhat做rank-r SVD后Riccati。这正是用户要求的识别流程。','',
        '独立核查150个最终联合OLS拟合、300个最终Riccati策略，原始设计矩阵lstsq与充分统计量OLS差异至多1.256e-15。重放rank2/full rank的30个原始CE正式seed至32768 OLS样本，2040个前缀策略与原输出逐元素相同；最大正规方程相对残差7.775e-16。时间对齐、动作符号、实际噪声残差和无噪声[A,B]恢复均通过。这些检查未发现CE识别/截断/评价链上的实现错误，不是对所有可能bug的形式化证明。','',
        '在共同131,328预算，rank2的B平方Frobenius误差由0.01899519降至0.00073809，约25.73倍；同rank控制gap由0.00933966降至0.00175250，约5.33倍。真实A替代Ahat而保持相同Bhat时，同rank截断gap收益约34.12倍；但跨rank full-dense/rank2-trunc的gap比仍仅5.95倍。A误差限制了同rank收益，跨rank控制几何的变化也不能忽略。干预只在Riccati输入替代参数，没有重新拟合“已知A估计器”。','',
        '另用30个相同的各向同性B误差方向、揭示真实A，排除OLS数据分布的变化：误差尺度0.01/0.02下，模型误差收益25.737/25.737倍，真实control gap收益6.027/6.026倍。这个独立干预说明模型误差到控制精度的映射随plant改变；模型误差收益不能直接充当sample-complexity比值。完整干预及配对置信区间见CE_IDENTIFICATION_AUDIT_20261019.md及保存的诊断图表。','',
        '**独立审计与真实运行开销。**','']
    for route in ('npg','pi'):
        q=formal['audits'][route]
        text.append(f'{route.upper()}正式策略核对{q["checked_policies"]:,}个，performance identity最大误差{q["performance_identity_max_error"]:.4g}，full-rank bitwise配对{q["full_rank_bitwise_pairs"]:,}个，PI actor重放{q["independent_PI_actor_replays"]:,}次。')
    stable=all(q['instability_rate']==0 and q['numerical_failures']==0 for q in rows)
    text += ['',f'全部正式单元均无策略不稳定与数值失败：{stable}。每个单元0/30不稳定的Wilson95%区间[0%,11.35%]。资源timeout与算法不稳定分开统计，所有失败与被取消作业均保留。', '',
        f'本轮{cost["job_records"]}个自身Slurm记录，实际allocated core-hours={cost["allocated_core_hours"]:.6f}，Slurm elapsed billing-unit hours={cost["elapsed_billing_unit_hours"]:.6f}，低于配置中的300核时上限。Reported TotalCPU hours={cost["reported_total_cpu_hours"]}；是否可用={cost["total_cpu_counter_available"]}。最大step RSS={peak_text}。这些核时不能直接当成AMS实际SU，账户Used & Pending余额也没有被当成实际消耗。', '',
        f'AMS匹配本轮实际作业{settled["matched_own_records"]}/{settled["expected_measured_nonzero_jobs"]}条；全部已测作业结算齐备={settled["all_measured_jobs_settled"]}。逐作业显示SU加总={settled["displayed_rounded_settled_SU_sum"]:.2f}（每行有小数舍入）；未结算作业不按零成本处理，其他账户成员作业明细未保留。','',
        f'费用估计有一项明确错误：55个申请7680MiB的PI作业，实际AMS全部按约2SU/小时计费，Slurm却显示billing=1。额外等价核时约{billing["extra_effective_core_hours_for_these_matched_PI_jobs"]:.6f}。原资源计划只按一核墙钟估算SU，低估了实际费用，不能说实际SU在300以内。原计划和费用误判一并保留。没有为这次核查启动新的计算作业。','',
        '官方[AMS计费规则](https://hprc.tamu.edu/kb/User-Guides/AMS/#non-exclusive-job)按内存向上取整计算有效核数，这与高内存作业收费增加一致。但现场maxconfig -f读取7680M试算脚本仍显示1，而实际AMS收费2；站点估算器的精确差异尚未完全定位，不能把某个尚未验证的内存阈值宣称为已确认结论。实际支出以逐作业AMS记录为准。TotalSlots是申请槽位，也不能误标成计费有效核数。','',
        f'已核对{execution["paired_learning_tasks"]}组学习对、{execution["learning_records_checked"]:,}条记录，实际学习尝试{execution["distinct_real_learning_attempts"]}个（最终producer作业{execution["distinct_real_learning_jobs"]}个；PI正式seed bundle共享父作业）。全部burn及Stein priming已计数。整个本轮物理模拟量上下界为{execution["entire_campaign_physical_transitions_bounds"]}，包含pilot、诊断及中断可能丢失/重放的步数。', '',
        '两次NPG正式资源超时：rank8/seed316第41次更新后、rank64/seed323第43次更新后，分别用原源码从完整断点补3次/1次更新，未换seed；原50分钟占用与续跑均计入费用。没有逐块日志的丢弃模拟量合计严格记为[0,67,109,904]，没有伪造精确零额外样本。', '']
    bounds=execution['execution_aware_sample_requirement_bounds'];unchanged=all(q['unchanged_under_discarded_work_bound'] for q in bounds)
    text += [f'把上述额外样本从零到上界全部计入，并允许策略gap非单调，逐预算成功包络核查的全部NPG/PI样本门槛及删失结论不变={unchanged}。主比较rank2与full rank本身没有资源中断。','',
        '原始曲线横轴统计参与估计的完整累计数据预算；资源丢弃开销另以execution_cost_success_envelopes.csv给出。唯一成功计数不确定的点为rank8截断NPG、target0.05、N=229,125,036：执行预算下为29至30/30成功（Wilson包络[83.33%,100%]），不能把原数据预算表中的30/30冒充精确执行开销下的计数。它仍高于27/30，N90不变，其余点成功计数不受这个开销区间影响。','',
        '其余运行问题均保留：初版预检把oracle目标误设为0.005导致48秒验证失败，改为0.025验证裕量，学习目标仍为0.1/0.05；PI最大内存预检超过保守guard后将后续请求改为7680MiB，没有OOM；一个PI pilot在完整输出提交后父作业timeout，独立审计通过后保留有效数据并保留失败费用；同模型误差辅助诊断首次timeout，优化I/O并逐方向checkpoint后完整重跑30方向，均不新增学习样本。','',
        f'本次额外发现并修正了{ratios["invalid_finite_ratio_CI_entries_corrected"]}条辅助比值CI显示：原报告在full-rank N有限而低rank N未达标时，把删失的分母N当作字面无穷大，使bootstrap比值显示0。审阅表对所有含删失N的比值标记为无法估计，原始报告保留；N的点估计、N区间、策略、成功率及所有有限比较均未改变。项目中的未来报告源码已修正，无学习重跑。','',
        '**交付文件。**','',
        f'- 完整原始结果及{archive["verified_hashed_files"]}文件hash清单：{root.as_posix()}；本地归档SHA256={archive["sha256"]}。',
        f'- 概览图、比值修订表、账目、transition审计、视觉检查及生成源码：{review.as_posix()}。',
        '- report-confirm：NPG/PI成功率0.1/0.05、absolute=relative gap曲线、所有seed检查点、样本复杂度和置信区间；joined-report：60单元总表与CE/NPG/PI原始总图。',
        '- 原CE完整结果：E:/ChatGPT/Results/LQR_experiments/ce-matched-initial-gap-20261018；新CE审计另存旧名matched-gap-npg-pi-20261019/ce-identification-audit，并包含在本轮完整归档。','']
    content='\n'.join(text)
    a.document.parent.mkdir(parents=True,exist_ok=True);a.document.write_text(content,encoding='utf-8')
    (review/'MATCHED_GAP_FINDINGS_ZH.md').write_text(content,encoding='utf-8')
    inputs=[root/'joined-report/all_algorithms_summary.json',root/'report-confirm/summary.json',
        review/'compute_accounting.json',review/'transition_and_execution_audit.json',root/'local_archive_verification.json',
        review/'settlement/own_settlement_summary.json',review/'billing_reconciliation.json',review/'visual_review.json',
        review/'reviewed_low_truncated_vs_full_dense.json',root/'system_verification.json']
    (review/'FINDINGS_PROVENANCE.json').write_text(json.dumps(dict(status='complete',
        inputs={str(p):sha(p) for p in inputs},source_sha256=sha(Path(__file__)),
        new_primitive_transitions=0,model_evaluations=0),indent=2)+'\n',encoding='utf-8')
    print(str(a.document))


if __name__=='__main__':main()
