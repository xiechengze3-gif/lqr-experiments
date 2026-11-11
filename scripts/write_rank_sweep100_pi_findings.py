"""Write the local experimental record from complete audited numeric artifacts."""
import csv
from pathlib import Path

from publish_rank_sweep100_results import read


ROOT=Path(__file__).resolve().parents[1]
cfg=read(ROOT/'configs/rank_sweep100_pi_20261017.json');out=Path(cfg['local_output'])
summary=read(out/'report-confirm/joined_summary.json');audit=read(out/'audit.json')
cost=read(ROOT/'receipts/rank-sweep100-pi-compute-accounting.json')
counts=read(out/'campaign_transition_accounting.json');provenance=read(out/'execution_provenance.json')
assert audit['status']=='PASS' and audit['source_tasks']==175
assert summary['status']=='complete' and summary['completed_tasks']==150
assert read(out/'visual_review.json')['status']=='PASS' and provenance['status']=='PASS'
baseline=Path(read(ROOT/'receipts/rank-sweep100-pi-20261017.json')['baseline_result'])
old=read(baseline/'report-confirm/summary.json')
eps=cfg['epsilon'];req=summary['requirements'];ranks=cfg['ranks']


def cell(route,method,rank,target=eps):
    return next(r for r in req if r['route']==route and r['method']==method and r['rank']==rank and r['epsilon']==target)


def budget(value):return 'NR' if value is None else f'{value:,}'


def link(label,relative):return f'[{label}]({(out/relative).as_posix()})'


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
                     ['| '+' | '.join(map(str,row))+' |' for row in rows])


main_rows=[];gap_rows=[];oracle_rows=[]
for rank in ranks:
    main_rows.append([rank]+[budget(cell(route,method,rank)['N_hat_epsilon_90'])
        for route in ('npg','ce','pi') for method in ('dense','truncated')])
    d,t=cell('pi','dense',rank),cell('pi','truncated',rank)
    gap_rows.append([rank,f"{d['max_budget_gap_median']:.9f}",f"{t['max_budget_gap_median']:.9f}",
        f"{d['max_budget_successes']}/30",f"{t['max_budget_successes']}/30"])
    pi=next(v for v in summary['oracle_summary'] if v['rank']==rank)
    npg=next(v for v in old['oracle_summary'] if v['rank']==rank)
    oracle_rows.append([rank,f"{pi['initial_gap']:.8f}",npg['exact_iterations'],
                        pi['exact_PI_iterations'],pi['exact_PI_sensitivity_iterations']])
with (out/'report-confirm/endpoint_exact_PI_cleanup_all_seeds.csv').open(encoding='utf-8-sig',newline='') as stream:
    cleanup=[r for r in csv.DictReader(stream) if r['phase']=='confirm']
assert len(cleanup)==300
primary1=sum(r['after_1_meets_primary']=='True' for r in cleanup)
half1=sum(r['after_1_meets_sensitivity']=='True' for r in cleanup)
max1=max(float(r['after_1_gap']) for r in cleanup);max2=max(float(r['after_2_gap']) for r in cleanup)
nr=[r for r in req if r['epsilon']==eps and r['N_hat_epsilon_90'] is None]
assert all(r['max_budget_success_rate']==0 for r in nr)
assert all(r['max_budget_instability_rate']==0 and r['max_budget_numerical_failures']==0 for r in req)
report=f"""# 100维 LQR rank sweep PI 实验结果

已完成独立的5-seed pilot和每个rank、每种PI方法30个新种子的正式实验。正式种子为100–129，pilot种子为0–4，二者分开统计。PI共175组配对、350条学习路径；原NPG/CE的30-seed结果通过文件哈希验证后合并，没有重跑其学习。完成日期为2026-10-18，结果目录为 `{out}`。

在这一个固定100维系统实例及已测预算上，Dense NPG和Dense PI在rank 2/8/32/64均未达到主目标，而rank100达标。Truncated PI在较低rank下需要更少的预算。曲线存在并列和中间rank较差的情形，数据不支持“rank越小，dense必然越难”的严格单调规律。

## 精度和样本门槛

主目标是共同的 **absolute optimality gap** `J(K)-Jstar <= {eps}`，即五个初始gap最小值的0.1倍；减半目标为 `{eps/2}`。J按W=I的无额外探索策略精确求解Lyapunov方程评估，不用含噪测试回报代替。relative gap仅用于辅助作图，定义为 `(J-Jstar)/(J0-Jstar)`。

下表均为含所有burn-in的primitive transitions。Nhat是第一个至少27/30成功的已测预算；NPG和PI要求截至该预算的整个策略路径稳定，CE要求该预算输出在真实系统上稳定。

{table(['rank','Dense NPG','Truncated NPG','Dense CE','Truncated CE','Dense PI','Truncated PI'],main_rows)}

NR表示not reached。NPG最大预算245,902,512，CE最大预算65,792，PI最大预算3,474,432。上表NR单元在最大预算均为0/30成功，精度失败率100%，Wilson95%区间为[88.65%,100%]，没有赋予有限Nhat。达到门槛的是经验成功率点估计；30/30的成功率Wilson95%区间仍为[88.65%,100%]，不等于总体成功概率大于0.9的95%置信保证。

所有PI有限Nhat单元在首次达标预算均为30/30，其2,000次配对种子曲线bootstrap区间在当前网格上退化到同一预算。网格之间的门槛仍未知。复用的Dense CE/r8区间为[16,640,24,832]，CE/r100两种方法均为[12,544,16,640]。完整的bootstrap上下界、删失标记、首次/持续达标预算、成功/失败/不稳定率区间见 {link('60行双精度样本门槛表','report-confirm/all_algorithms_sample_complexity.csv')}；{link('按rank汇总表','report-confirm/all_algorithms_summary_table.csv')}同时包含初始gap、oracle步数及各方法区间。

## PI终点误差和敏感性

下表的gap是统一四次更新、最大预算3,474,432后的中位数，区别于“首次达到目标时”的gap。

{table(['rank','Dense PI gap','Truncated PI gap','Dense主目标成功','Truncated主目标成功'],gap_rows)}

减半目标下，Truncated PI在rank2/8/32的Nhat依次为 {budget(cell('pi','truncated',2,eps/2)['N_hat_epsilon_90'])}、{budget(cell('pi','truncated',8,eps/2)['N_hat_epsilon_90'])}、{budget(cell('pi','truncated',32,eps/2)['N_hat_epsilon_90'])}；rank64/100均NR。Dense PI的五个rank全部NR，最大预算成功率均0/30。更严格目标下没有有限dense PI门槛可用于完整的rank排序。NPG/CE的减半目标结果也保留在上述双精度表中。

全部正式PI路径稳定且无数值求解失败；每个单元0/30不稳定的Wilson95%区间为[0%,11.35%]。精度失败和数值/失稳失败分别统计。gap曲线显示稳定观测的中位数和IQR，成功率曲线始终保留所有30个种子。

## 优化难度和现象解释

{table(['rank','初始gap','Exact NPG主目标步数','Exact PI主目标步数','Exact PI减半目标步数'],oracle_rows)}

NPG统一eta=0.05、44次更新；PI统一四次greedy更新。初始exact-gradient NPG和finite-H population oracle都只需6/11/17/20/21步达主目标，Exact PI均只需一步。因此所测初始无噪声路径的迭代上限足够。

对全部300个正式PI终点，追加一步真实PI后，主目标成功数为{primary1}/300，减半目标成功数为{half1}/300，最大gap仅{max1:.6g}；两步后最大gap为{max2:.6g}。这是独立的事后模型oracle诊断，不修改采样策略或Nhat，也不计作可实施算法。{link('全部终点oracle数据','report-confirm/endpoint_exact_PI_cleanup_all_seeds.csv')}保留逐种子结果。

初始oracle仍不能完全排除噪声诱发的后程优化瞬态。K0没有真实无效动作分量，初始真梯度轨迹不会探测采样噪声后来激发的方向。既有NPG终点诊断覆盖全部300个正式终点：Dense r2/8/32/64分别再需3/4/7/6步真实梯度才达到至少27/30成功；Truncated r32/64需4/5步。真实oracle介入同时移除了估计噪声，不能单独分离优化与估计的贡献。

事后按真实动作空间分解，Dense PI在r2/r8的无效动作直接损失占gap的中位比例为98.93%/95.46%，Truncated为6.33%/3.87%；有效控制损失接近。这支持这些配对实验中截断减少错误动作代价的解释。真实子空间只用于该诊断，不提供给学习更新。{link('损失分解','report-confirm/endpoint_loss_decomposition_summary.csv')}和逐种子数据均已保存。

总体上，PI的rank-aware版本在主目标下把门槛变为328,192/328,192/1,377,024/3,474,432/3,474,432的阶梯。NPG的收益集中在r2/r8，r32/r64仍删失；CE的dense门槛也有较低rank相对full rank更高的局部现象，但整体非单调，部分bootstrap区间重叠。**这些是本实例的empirical observations。** 增加rank同时改变控制能力、Jstar和探索状态分布：总随机输入方差400固定，进入状态的协方差 `4 B_r B_r.T` 随rank变化。跨rank趋势不能单独归因于estimator，也不能据五个网格点宣称通用rank复杂度律。

## 系统和冻结协议

固定n=m=100，Q=R=W=I，b=1；一次生成共同U/V并使用 `B_r=U[:,:r] V[:,:r].T`。沿用完全相同的已验证A/K0/F0/P0/J0及系统NPZ字节，rho(A)=1.2，rho(F0)=0.75，J0=127.55538085。`A-B_r K0=F0`最大元素误差2.78e-17，共同Lyapunov证书残差7.11e-15。初始gap列于上表，全部rank都可稳定控制。

PI复用完整的原坐标average-cost off-policy LSTD，200维联合(x,u)二次critic共20,100个系数。无样本白化、ridge或critic降秩。统一rtol=1e-6，统一GMRES尝试(100,20)再(200,20)。提取G=Huu-R、C=Hux；Dense对G作既有PSD处理，Truncated先从[G,C]估计rank-r共同左空间，再作相同PSD处理；greedy增益为 `(R+G)^-1 C`。真实U/V不进入学习更新。

sigma=2、每次更新burn256，四个fresh batch为65,536/262,144/1,048,576/2,097,152；累计预算为65,792/328,192/1,377,024/3,474,432。轨迹在更新间连续。首轮配对共享同一个原始critic；分叉后使用相同估计器和配对外生随机源，各自状态可不同。跨rank随机源不含rank标签。rank100跳过SVD并共享相同计算。

NPG和PI沿冻结的增长batch轨迹读取预算前缀，更新次数与预算一起增加；这不是固定迭代数后只改变batch的扫描。所有同一算法超参数和采样协议跨rank一致。完整科学配置与独立资源修订分别保存，避免把调度时限变化混为学习参数变化。

## 执行和完整性

正式Slurm数组20184820包含30个相同seed bundle，每个任务依次调用五个原始rank子任务，各在独立Python进程中执行；资源为1CPU、7GB、medium、228分钟，最多30并发。全部正式任务COMPLETED，归档作业20184821也COMPLETED。新增PI实际占用 **{cost['allocated_core_hours']:.6f} Slurm核时**，billing-unit hours同值，TotalCPU为{cost['reported_total_cpu_hours']:.6f}核时；包含诊断、超时和续跑。初稿规划125核时随后按实测修订为140核时，正式提交前的最坏总申请137.936667核时；实际未超上限。原NPG/CE的112.978889核时另计。Slurm占用与AMS已结算SU区分保留。

运行问题均保留：最大batch旧预检曾OOM，已完成r2记录保存，之后采用显式GC、磁盘观测和持久化critic；V2最大batch实测峰值6.67GiB。8k I/O块在pilot前统一改为64k并通过原始观测等价验证。初始pilot发生19次40分钟TIMEOUT，第一轮恢复又有13次TIMEOUT，其中2个已提交完整有效输出；仅恢复实际缺失组，最终25组pilot齐全，无种子替换。正式阶段采用seed bundle共享时限后没有资源中断。无效分区/CRLF提交被拒时尚未创建作业；共享SSH认证失效由用户登录恢复，远端运行未被停止。

独立审计通过{audit['source_tasks']}组、{audit['policy_checkpoints_checked']:,}个策略checkpoint和{audit['critic_updates_replayed']:,}次critic到actor更新重放；代价最大重算差{audit['maximum_quality_recompute_difference']:.6g}，actor最大重放差{audit['maximum_actor_replay_difference']:.6g}。rank100共35组critic与全部策略逐元素相同；全部175组首轮估计配对也一致。全部八张正式PNG均已实际视觉检查，SVG副本有效；图表数据、配置和来源哈希保留。

正式唯一模拟量精确为{counts['confirmation_unique_physical_transitions']:,} transitions，按两种方法分别计入预算的总和为{counts['confirmation_algorithm_charged_transitions']:,}。含pilot的已提交唯一数据为{counts['main_unique_physical_transitions']:,}，按算法计数为{counts['main_algorithm_charged_transitions']:,}。pilot超时前未提交最后chunk缺少逐次快照，额外重复执行量仅能保守界定为0–{counts['pilot_possible_uncommitted_reexecuted_transitions_upper']:,}；旧OOM预检也保留上下界。整个PI补充实际模拟总量为 **[{counts['entire_PI_supplement_physical_lower']:,}, {counts['entire_PI_supplement_physical_upper']:,}]**，上界不代表所有可能重放都发生。正式门槛没有恢复重放歧义。所有诊断与本机oracle复算均不进入正式成功率分母，模型oracle不新增学习transitions。

## 文件

主要图为 {link('Sample complexity vs rank','report-confirm/sample_complexity_vs_rank_all_algorithms.png')}、{link('Success probability vs budget','report-confirm/all_algorithms_success_probability.png')}、{link('Absolute gap','report-confirm/all_algorithms_absolute_gap_convergence.png')}、{link('Relative gap','report-confirm/all_algorithms_relative_gap_convergence.png')}，各有SVG；PI单独的三类曲线和oracle曲线也在同目录。

{link('数值审计','audit.json')}、{link('图表检查','visual_review.json')}、{link('模拟量核算','campaign_transition_accounting.json')}、{link('真实作业与每组数据的对应表','execution_provenance_by_pair.csv')}、{link('计算占用','compute_accounting/rank-sweep100-pi-compute-accounting.json')}、{link('问题记录','run_issues.json')}构成检查入口。raw/policies/critics/checkpoints/frozen及归档中的source目录保存原始结果、完整估计器、策略、断点、系统和冻结源码。原始TAR.GZ保持不变，local-review ZIP补充本地审计、联合表图、文档和核算；各自大小和SHA256见delivery_receipt.json。
"""
path=ROOT/'docs/RANK_SWEEP100_PI_FINDINGS_20261018.md'
path.write_text(report,encoding='utf-8');print(path,flush=True)
