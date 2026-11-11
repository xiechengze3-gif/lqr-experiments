# CE：匹配初始optimality gap的实测对照

已完成5-seed pilot与每rank30个新种子200–229的正式实验，pilot不进入正式分母。所有原始数据、配置、策略、断点、最终OLS充分统计量、图表和作业记录均保留。

匹配初始gap后，在relative target 0.1下，rank2 truncated需要3,328 transitions，full-rank dense需要14,592，低rank端节省4.38倍；rank8节省1.73倍，rank32/64仍未胜过full rank，整体不单调。更严格target 0.05下主比较节省4.52倍。

## 精度与主比较

所有rank的初始gap固定为1，最大数值偏差为2.13e-13。因此relative target 0.1/0.05同时对应共同absolute gap 0.1/0.05。

| rank | 初始gap | Dense CE N(0.1) | Truncated CE N(0.1) | full dense / low truncated | 配对bootstrap95%区间 |
|---|---|---|---|---|---|
| 2 | 1 | 14,592 | 3,328 | 4.385 | [4.384615384615385, 4.384615384615385] |
| 8 | 1 | 16,640 | 8,448 | 1.727 | [1.7272727272727273, 1.7272727272727273] |
| 32 | 1 | 24,832 | 16,640 | 0.877 | [0.7037037037037037, 0.8769230769230769] |
| 64 | 1 | 20,736 | 20,736 | 0.704 | [0.7037037037037037, 0.7037037037037037] |
| 100 | 1 | 14,592 | 14,592 | 1.000 | [1.0, 1.0] |

Nhat是已测预算中至少27/30输出在真实系统稳定且达标的最小预算；全部burn-in计入。区间基于2,000次完整配对种子曲线bootstrap。离散网格仍有分辨率限制；主比较的bootstrap区间退化到当前网格门槛，不代表连续最小样本量已精确识别。NR保留为删失，不赋有限门槛。

主目标首次预算的rank2 truncated为29/30成功，Wilson95%区间[83.33%,99.41%]；full-rank dense为30/30，区间[88.65%,100%]。Nhat表示经验成功率至少0.9，不等于总体成功率下界达到0.9的95%置信保证。

## 更严格目标与同预算误差

| rank | Dense N(0.05) | Truncated N(0.05) | full dense / low truncated |
|---|---|---|---|
| 2 | 28,928 | 6,400 | 4.52 |
| 8 | 33,024 | 14,592 | 1.9824561403508771 |
| 32 | 49,408 | 33,024 | 0.875968992248062 |
| 64 | 49,408 | 49,408 | 0.5854922279792746 |
| 100 | 28,928 | 28,928 | 1.0 |

最大预算为131,328 transitions。同预算中位gap如下；Delta0=1使relative与absolute数值相同。

| rank | Dense gap | Truncated gap | full-rank dense gap / truncated gap |
|---|---|---|---|
| 2 | 0.00933966 | 0.00175250 | 5.526 |
| 8 | 0.01141407 | 0.00495027 | 1.956 |
| 32 | 0.01518160 | 0.01208995 | 0.801 |
| 64 | 0.01386534 | 0.01309728 | 0.739 |
| 100 | 0.00968452 | 0.00968452 | 1.000 |

成功率及Wilson95%区间保存在report-confirm/success_by_budget.csv，所有gap与配对区间保存在fixed_budget_gaps.csv。

## 构造与解释边界

保持上一轮完全相同的物理A、B_r、Q=R=W=I与共同U/V。使用同一独立满秩随机正交D构造K0_r=Kstar_r+alpha_r D，并在采样前按真实gap校准alpha。真最优增益只用于构造初始策略，不提供给OLS/DARE学习更新。所有K0均满秩。

这轮K0确实用于CE行为采样，不能复用上一轮的学习轨迹来冒充新实验。不同rank的初始闭环与探索状态分布仍不同；匹配初始gap消除了相对精度分母差异，不能识别纯估计器因果效应。一套共同物理系统、30个配对数据种子的结果不能推出普遍单调rank定律。

## 完整性与资源

预检无噪声OLS恢复与两次断点恢复比较通过；全部6,750个保存策略经真实Lyapunov代价和performance-difference identity核对。full rank的675个配对预算逐元素相同。

本轮179个Slurm计费记录全部终态完成；实际占用0.589722核时，billing-unit hours为0.589722，低于8核时上限。它是本轮自有作业的实测占用，不等同于账户全部AMS消耗。

pilot物理transitions=3,283,200，正式=19,699,200，预检诊断=267,776，总计=23,250,176。两种CE后处理共享数据，算法预算各自计入，但物理模拟不双计。未新增本机学习或采样。

运行记录：共享SSH在沙箱外正常可用；冻结输入哈希、AST与LF脚本校验通过。归档SHA256和全部原始文件清单已校验。图表视觉检查在交付前另存visual_review.json。

原始归档和本地补充文件分别保存，原有NPG/CE/PI结果没有修改。

## 图与数据

[样本需求](E:/ChatGPT/Results/LQR_experiments/ce-matched-initial-gap-20261018/report-confirm/sample_complexity_vs_rank.png)、[成功率曲线](E:/ChatGPT/Results/LQR_experiments/ce-matched-initial-gap-20261018/report-confirm/success_probability_vs_budget.png)、[gap曲线](E:/ChatGPT/Results/LQR_experiments/ce-matched-initial-gap-20261018/report-confirm/relative_and_absolute_gap_convergence.png)、[同预算直接跨rank比较](E:/ChatGPT/Projects/LQR_experiments/analysis/ce-matched-initial-gap-20261018/reviewed_figures/low_rank_truncated_vs_full_rank_dense.png)。图表有SVG副本；最后一图仅改善图例和坐标标签，原始图与CSV保持不变。

[样本需求与置信区间](E:/ChatGPT/Results/LQR_experiments/ce-matched-initial-gap-20261018/report-confirm/sample_complexity.csv)、[跨rank收益](E:/ChatGPT/Results/LQR_experiments/ce-matched-initial-gap-20261018/report-confirm/low_rank_vs_full_rank.csv)、[实际作业映射](E:/ChatGPT/Results/LQR_experiments/ce-matched-initial-gap-20261018/execution_provenance.json)。自动审批服务曾暂时容量不足和超时；未执行的命令均记录，后经同一审批流程恢复，实验任务未受影响。

附加审阅包保存于E盘项目的analysis目录。自动审批服务未能完成把附加文件写回结果目录的检查，因此原始结果目录保持已经校验的版本；本地审阅说明、图表修订和完成回执在授权工作区另存。该异常没有影响实验运行或原始数据。
