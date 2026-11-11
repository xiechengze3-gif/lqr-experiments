# 初始gap归一化：CE/NPG已有结果补充（2026-10-28）

逐次定义 relative=(J(K)-Jstar)/(J(K0)-Jstar)，先归一化再汇总；absolute为J(K)-Jstar。
读取全部96,600个已保存输出和2,064个已有任务基线；新增学习运行、训练transitions及控制求解均为0。
相对精度为10%/3%/1%。每个设置的全24重复中至少22个达标才记该预算达到90%观察成功率。
失稳作为正无穷纳入；未达标记NR并保留最大已测预算，不删除失败、不插值、不外推。
不同设置的相对目标对应不同绝对容差；二者是在回答不同的精度问题。
全部228条NPG失稳路径及其8690个失败阶段输出保留。原absolute预算144行逐项完全复现。

## 固定r=2、epsilon=0.1：absolute与relative并列

|A|算法|n|方法|初始gap中位数|absolute达标预算|relative达标预算|relative最大预算成功数/24|
|---|---|---:|---|---:|---:|---:|---:|
|scalar|CE|12|dense|0.401102|1,680|3,216|24|
|scalar|CE|12|truncated|0.401102|528|1,680|24|
|scalar|NPG|12|dense|0.401102|9,344,808|20,355,948|23|
|scalar|NPG|12|truncated|0.401102|5,018,652|10,917,828|24|
|scalar|CE|24|dense|0.401102|6,288|12,432|24|
|scalar|CE|24|truncated|0.401102|912|3,216|24|
|scalar|NPG|24|dense|0.401102|NR|NR|0|
|scalar|NPG|24|truncated|0.401102|25,075,008|NR|0|
|scalar|CE|48|dense|0.401102|24,720|NR|0|
|scalar|CE|48|truncated|0.401102|1,680|3,216|24|
|scalar|NPG|48|dense|0.401102|NR|NR|0|
|scalar|NPG|48|truncated|0.401102|NR|NR|0|
|dense|CE|12|dense|0.49271|1,680|3,216|24|
|dense|CE|12|truncated|0.49271|528|912|24|
|dense|NPG|12|dense|0.49271|9,344,808|17,209,908|24|
|dense|NPG|12|truncated|0.49271|5,018,652|9,344,808|24|
|dense|CE|24|dense|0.500055|6,288|12,432|24|
|dense|CE|24|truncated|0.500055|912|1,680|24|
|dense|NPG|24|dense|0.500055|NR|NR|0|
|dense|NPG|24|truncated|0.500055|NR|NR|0|
|dense|CE|48|dense|0.500479|24,720|NR|0|
|dense|CE|48|truncated|0.500479|1,680|3,216|24|
|dense|NPG|48|dense|0.500479|NR|NR|0|
|dense|NPG|48|truncated|0.500479|NR|NR|0|

## 已完成图表与完整记录

主图：figure_ce_absolute_relative、figure_npg_absolute_relative、figure_fixed_precision_budgets；同时保存PNG与SVG。
耦合A复现、n24的四秩扫描、两类满秩谱及平坦谱均有并列图；所有设置和方法都保留在完整统计表。
attainment_side_by_side.csv给出同一个数值epsilon下两种定义的预算，以及相对目标对应的绝对容差范围。
per_run_attainment_and_censoring.csv保留全部个体未达标和失稳记录；NPG另给连续4点确认预算。
首个达标点是离线评估，不改变原输出、停止点或迭代。首次达标不保证所有后续点持续达标；个体后续失稳标志单独保存。
误差带仅在全部24重复稳定时绘制稳定样本IQR；部分失败时仍用失败计入后的中位数，绝不以幸存者中位数替换。
本归一化没有改变任何同一系统的dense/truncated逐对gap倍率；跨系统聚合排序和固定精度预算可以改变。
如果初始gap为0，该归一化未定义；本数据所有基线严格为正，未使用分母截断。
所有原始输入哈希在前后均核对一致；费用由本后处理作业单独记录，不声称新增了学习证据。
