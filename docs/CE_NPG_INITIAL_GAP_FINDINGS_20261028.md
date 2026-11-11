# CE/NPG 初始gap归一化补充：已有结果后处理（2026-10-28）

**已经完成，未重新运行学习实验。** 本次逐条复用全部96,600个保存输出及2,064个已有任务基线，
将 absolute gap 与初始gap归一化结果并列展示，并补齐两种口径的固定精度预算。
新增学习运行、训练transitions、新策略评价和控制方程求解均为0。

## 指标与统计口径

对每个具体系统、每个重复，使用原稳定初始策略K0定义

\[
 g_0=J(K_0)-J_\star,\qquad
 g(K)=J(K)-J_\star,\qquad
 e_{\mathrm{rel}}(K)=\frac{g(K)}{g_0}.
\]

先逐个输出归一化，再按完整24个重复汇总，未用“两个总体中位数之比”代替。
同一物理系统内所有方法共享g0，所有g0严格为正，范围0.200551–3.208818；
没有分母截断。逐条计算与已保存relative_gap列完全一致，最大差异为0。

两种口径都用数值阈值epsilon=0.1、0.03、0.01，首个已测预算上至少22/24成功才记达标。
相对10%表示剩余gap不超过初始可改善损失的10%，即消除至少90%初始gap；
不是额外成本占Jstar的10%。相对epsilon的绝对容差为epsilon*g0，二者不是相同物理精度。

失败按正无穷计入中位数及成功率。NPG失稳后所有计划阶段继续失败。
未达标保留最大已测预算并记NR（右删失），不删掉、不插值、不外推有限预算。
原有144行absolute达标预算逐项完全复现。

## 主图：absolute与relative并列

- CE 三维度学习图：[PNG](../local_runs/ce-npg-initial-gap-20261028/report/figure_ce_absolute_relative.png) · [SVG](../local_runs/ce-npg-initial-gap-20261028/report/figure_ce_absolute_relative.svg)。
- NPG 三维度学习图：[PNG](../local_runs/ce-npg-initial-gap-20261028/report/figure_npg_absolute_relative.png) · [SVG](../local_runs/ce-npg-initial-gap-20261028/report/figure_npg_absolute_relative.svg)。
- 两种固定精度预算：[PNG](../local_runs/ce-npg-initial-gap-20261028/report/figure_fixed_precision_budgets.png) · [SVG](../local_runs/ce-npg-initial-gap-20261028/report/figure_fixed_precision_budgets.svg)。

学习图上排absolute、下排relative，列为n=12/24/48、r=2。
预算图左列absolute、右列relative，上排CE、下排NPG。
所有横轴均保留原累计transitions，包含原有burn-in和baseline。
CE的归一化分母是K0的gap，不是首个拟合输出的gap；没有补造一个CE的M=0学习输出。
NPG原先保存的stage0归一化值为1。

图中∞表示失败计入后的中位数无穷大，不用幸存者中位数替换；数字显示终端稳定数/24。
阴影仅在该点全部24重复稳定时展示IQR。
预算图空心三角表示在最大已测预算仍未达标，不是已达到该精度的预算。
多个方法/阈值在同一预算删失时三角可能重叠，所有条件逐项保留在CSV中。

## epsilon=0.1 的具体预算

以下全部采用全24重复中至少22个达标，单位为primitive transitions。
每格顺序为 dense / truncated，NR表示未达标，不能据此计算一个有限加速倍率。

|A|算法|n，r=2|absolute预算：dense / truncated|relative预算：dense / truncated|
|---|---|---:|---:|---:|
|0.5I|CE|12|1,680 / 528|3,216 / 1,680|
|0.5I|CE|24|6,288 / 912|12,432 / 3,216|
|0.5I|CE|48|24,720 / 1,680|NR / 3,216|
|耦合A|CE|12|1,680 / 528|3,216 / 912|
|耦合A|CE|24|6,288 / 912|12,432 / 1,680|
|耦合A|CE|48|24,720 / 1,680|NR / 3,216|
|0.5I|NPG|12|9,344,808 / 5,018,652|20,355,948 / 10,917,828|
|0.5I|NPG|24|NR / 25,075,008|NR / NR|
|0.5I|NPG|48|NR / NR|NR / NR|
|耦合A|NPG|12|9,344,808 / 5,018,652|17,209,908 / 9,344,808|
|耦合A|NPG|24|NR / NR|NR / NR|
|耦合A|NPG|48|NR / NR|NR / NR|

标量A的r2族g0约0.401102，因此relative≤0.1对应absolute≤0.0401102，
比absolute≤0.1严格。n24/r2的truncated NPG达到旧absolute阈值，
但没有达到相对初始gap10%的阈值，这是不同精度问题，不是结果被改写。
耦合A的r2初始gap约0.49–0.50，按每个系统自己的准确值归一化，未统一替换成近似0.5。

同一个系统内的dense/truncated逐对gap倍率不受共同正分母影响；
跨系统汇总的中位数之比与固定精度预算可以变化。
归一化不会改变失稳事实，也不会使此前未达到高精度的NPG高维单元自动达标。

NPG最终相对初始gap的全分母中位数进一步说明这一点：

|A|n，r=2|Dense|Truncated|
|---|---:|---:|---:|
|0.5I|12|0.07426|0.03175|
|0.5I|24|∞|0.22667|
|0.5I|48|∞|∞|
|耦合A|12|0.05857|0.02744|
|耦合A|24|0.73095|0.18678|
|耦合A|48|∞|0.95365|

48维耦合A的truncated NPG虽然全部稳定，仍剩约95.4%的初始gap，
不能将稳定性改善等同于高精度学习。上述数值均先逐实例归一化再取中位数，
不是将旧的gap中位数除以初始gap中位数。

## 完整覆盖与失稳、未达标记录

共生成1,038行“设置×指标×阈值”的全分母统计和24,912行逐运行阈值记录。
在每种指标各519个条件中，absolute有285项未达标，relative有355项未达标。
全部228条NPG失稳路径及其8,690个失败阶段输出保留；没有补种子或选取最佳迭代。

- [absolute/relative预算并列表](../local_runs/ce-npg-initial-gap-20261028/report/attainment_side_by_side.csv)：同时给出相对目标对应的absolute容差范围。
- [完整全分母阈值表](../local_runs/ce-npg-initial-gap-20261028/report/attainment_absolute_relative.csv)：含达标人数、最大预算成功人数、稳定人数与删失标志。
- [全部逐运行达标和删失记录](../local_runs/ce-npg-initial-gap-20261028/report/per_run_attainment_and_censoring.csv)：含首次达标、NPG连续4点确认、后续失稳标志。
- [全部未达标条件](../local_runs/ce-npg-initial-gap-20261028/report/censored_cohorts.csv)、[全部失败输出](../local_runs/ce-npg-initial-gap-20261028/report/failed_outputs_preserved.csv)。
- [逐输出归一化值](../local_runs/ce-npg-initial-gap-20261028/report/normalized_records.csv)、[各任务真实初始gap](../local_runs/ce-npg-initial-gap-20261028/report/initial_gap_by_task.csv)。

首次达到阈值不保证以后一直达到；它只是离线评价，不改变原运行的停止点或输出。
逐运行表中另列首次达标后失稳、终端是否达标及4点确认，不能将这些定义混为一谈。

## 附录图

- 耦合A：[CE维度学习](../local_runs/ce-npg-initial-gap-20261028/report/appendix_figure_ce_absolute_relative.png)、[NPG维度学习](../local_runs/ce-npg-initial-gap-20261028/report/appendix_figure_npg_absolute_relative.png)、[预算并列](../local_runs/ce-npg-initial-gap-20261028/report/appendix_figure_fixed_precision_budgets.png)。
- n24秩扫描：[CE标量A](../local_runs/ce-npg-initial-gap-20261028/report/appendix_ce_rank_absolute_relative_scalar.png)、[CE耦合A](../local_runs/ce-npg-initial-gap-20261028/report/appendix_ce_rank_absolute_relative_dense.png)、[NPG标量A](../local_runs/ce-npg-initial-gap-20261028/report/appendix_npg_rank_absolute_relative_scalar.png)、[NPG耦合A](../local_runs/ce-npg-initial-gap-20261028/report/appendix_npg_rank_absolute_relative_dense.png)。
- 满秩两谱：[标量A](../local_runs/ce-npg-initial-gap-20261028/report/appendix_fullrank_absolute_relative_scalar.png)、[耦合A](../local_runs/ce-npg-initial-gap-20261028/report/appendix_fullrank_absolute_relative_dense.png)。
- [平坦谱负对照](../local_runs/ce-npg-initial-gap-20261028/report/appendix_flat_absolute_relative.png)。

以上全部同时交付SVG；完整表包含未在主图单独绘制的全部方法、秩及尾强度设置。
初始gap归一化只补充比较口径，不改变[原完整结论](CE_NPG_ARGUMENT_FINDINGS_20261028.md)
关于高维失稳、有效秩、经验adaptive CE及理论适用条件的限制。

## 验证与费用

唯一报告作业20330757在Grace计算节点完成，1 CPU / 2GiB / billing=1，实际80秒，
新增分配 **0.022222核时**；请求上限6分钟、0.1核时。
此前学习研究实际5.870833核时单独保留，不重复计费或计为新实验。
本次没有读取raw轨迹、生成探索噪声、更新策略或求解控制方程。
原三份输入文件前后SHA256不变；原学习源码、原图和原完成收据均保持不变。

36个报告文件逐SHA256通过，13张PNG已逐图检查。
[后处理协议](CE_NPG_INITIAL_GAP_PROTOCOL_20261028.md)、
[报告源码](../scripts/ce_npg_initial_gap_postprocess.py)、
[完成收据](../receipts/ce-npg-initial-gap-20261028-complete.json)、
[校验收据](../receipts/ce-npg-initial-gap-20261028-local-verification.json)。
完整归档：[delivery.tar.gz](../local_runs/ce-npg-initial-gap-20261028/delivery.tar.gz)。
