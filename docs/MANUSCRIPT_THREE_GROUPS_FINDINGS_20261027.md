# 三组主实验已完成（2026-10-27）

本轮直接覆盖用户要求的三组实验，未混用历史实验。576条正式采集轨迹全部完成，
每设置24个重复（3个系统种子×8个采样种子）。CE共288条共同数据轨迹，NPG共288条
各自连续的学习轨迹；产生24,864条相关的前缀/策略输出，不将它们称为独立重复。
全部CE输出及NPG策略均稳定，无求解失败、失稳、自动重试或真实cost选优。

结果支持严格低秩的维度分离和冗余噪声机制，也支持满秩时随预算变化的偏差/方差权衡。
自适应CE在多数设置接近合适固定秩，但有明确落后点；固定低秩NPG在平滑谱高预算下反而更差。

## 1. Exact-rank CE：维度收益与真实冗余机制

统一Q=R=W=I、K0=0、r=2、m=n。A分别为0.5I和独立随机稠密0.5O；
B的左右奇异基独立随机旋转。每个seed只采一条探索轨迹，各前缀只拟合一次完整模型，
dense、已知真实秩的截断和adaptive共享拟合。真实输入子空间只用于离线诊断。

固定N/(n+m)=64的结果如下。倍率为24个配对dense/truncated gap比的中位数，
与两个总体中位数之比略有不同。区间采用系统/采样两层bootstrap，只有3个系统种子。

|A族|n/r|dense gap中位数|truncated gap中位数|配对倍率及95%区间|
|---|---:|---:|---:|---:|
|0.5I|6|0.05103|0.01332|3.79 [3.00,4.48]|
|0.5I|12|0.11007|0.01624|6.81 [6.06,7.52]|
|0.5I|24|0.22086|0.01715|12.90 [11.89,14.08]|
|0.5I|48|0.45033|0.01721|26.49 [25.07,27.74]|
|dense|6|0.04760|0.01388|3.51 [3.04,3.98]|
|dense|12|0.10712|0.01844|5.65 [5.32,7.88]|
|dense|24|0.21900|0.01827|11.94 [11.36,13.65]|
|dense|48|0.44123|0.01847|24.17 [22.77,25.34]|

n=96、标量A时，dense真实redundant cost中位数为0.43452，截断为0.001211。
配对总gap改善中位数0.43333，配对redundant cost下降中位数0.43336。
这直接把性能收益与无效输入方向上的额外代价联系起来。稠密A有相同趋势。
估计子空间截断的真实redundant cost非零；不能把它写成真实子空间投影。

- 主图：[标量A](../local_runs/manuscript-three-groups-20261027/report/figure1_exact_ce_scalar.png)、[稠密A](../local_runs/manuscript-three-groups-20261027/report/figure1_exact_ce_dense.png)。
- [全维度预算曲线](../local_runs/manuscript-three-groups-20261027/report/figureS_exact_all_dimensions_scalar.png)。
- [逐配对机制表](../local_runs/manuscript-three-groups-20261027/report/exact_redundant_mechanism.csv)、[倍率区间](../local_runs/manuscript-three-groups-20261027/report/paired_effects_bootstrap.csv)。

图注：每点24重复，gap为绝对J(K)-Jstar，阴影为IQR。a/b取n=48，
横轴计入144步burn-in；c固定回归N/(n+m)=64，r=2。已知秩截断显式使用真实r，
adaptive仅使用数据split误差代理，所有学习方法均不使用真实输入子空间。

## 2. 满秩CE：有效秩与未知秩适应

n=m=16，分别采用(1,1,.05,...,.05)和.7^j两个全部奇异值非零的谱。
同一个系统内扫描k=0/1/2/3/4/6/8/12/16和7档预算，最高k就是dense。
自适应阈值为两半数据B估计之差的谱范数的一半；乘数1在正式运行前固定。

标量A、两段谱在N=256时，dense gap为0.65295，k2为0.14233，adaptive为0.14971；
但N=16384时，dense已达0.00910，adaptive仍为0.01773，不能声称逐点贴合oracle。
最高N=65536时，adaptive保留16阶，gap0.002349，接近dense的0.002284。

平滑谱的经验最佳固定k随N从256增至65536由3经4/6/8增至16；
adaptive的保留秩中位数由3增至11。N=1024时，最佳固定k6 gap0.11797，
adaptive为0.11962，dense为0.14666。固定k2/k4在高预算下留下明显偏差平台。
稠密A重现这些趋势。

这里的oracle是“各固定k总体中位数的最小值”，adaptive逐seed选k，
所以其总体中位数偶尔更低并不矛盾。记录了所有tau_k²和k(n+m)/N+tau_k²，
补图使用独立纵轴对照未标定的上界形状，不把它当成精确的cost或最优k预测器。
split代理没有被验证为理论置信半径，本轮是数据驱动阈值的经验评价。

- 主图：[标量A](../local_runs/manuscript-three-groups-20261027/report/figure2_approximate_ce_scalar.png)、[稠密A](../local_runs/manuscript-three-groups-20261027/report/figure2_approximate_ce_dense.png)。
- [偏差/方差对照](../local_runs/manuscript-three-groups-20261027/report/figureS_bias_variance_scalar.png)、[秩与包络表](../local_runs/manuscript-three-groups-20261027/report/approximate_rank_envelopes.csv)。

图注：第一列在固定数据前缀内扫描k；第二列比较dense、预设固定k2/k4与adaptive；
第三列给出所选秩及仅供离线诊断的经验最佳固定k。没有正式数据上的阈值调参。

## 3. 单轨迹NPG：收益及固定截断的边界

n=m=12，exact-rank、两段满秩及平滑满秩谱各自比较dense/truncated。
每臂一条连续轨迹，无resets；配对外生噪声，不把分叉后的轨迹称为同一批数据。
实现pulse/adjacent-return Stein回归，截断未知Zhat，保留已知RK。
H=12、每阶段12个pulse burn blocks和一个baseline，48阶段共25,075,008次转移/臂。
所有burn/baseline/block均计入。固定k分别为2/2/4，两臂步长均1/9。

|A族|谱|dense最终gap中位数|truncated最终gap中位数|每臂稳定数|
|---|---|---:|---:|---:|
|0.5I|exact|0.029785|0.012735|24/24|
|0.5I|两段满秩|0.029894|0.023852|24/24|
|0.5I|平滑满秩|0.027805|0.039814|24/24|
|dense|exact|0.029004|0.013508|24/24|
|dense|两段满秩|0.028696|0.020552|24/24|
|dense|平滑满秩|0.027358|0.040625|24/24|

严格低秩最终gap降低约2.34倍（标量A）和2.15倍（稠密A），两段谱也有收益。
平滑谱的k4在前段节省噪声，高预算时被dense反超，说明截断偏差确实会限制精度。
早期小batch下两臂gap均先增后降；不能把本轮写成逐步单调下降或已验证定理的
全部矩阵不变区域。排程预先固定，没有真实cost选迭代或拒绝更新。

第一阶段两臂确实共享K0和同一批blocks，数值已逐配对核对一致：标量A exact时，
截断前后Frobenius误差平方中位数21.287/10.231，下一步真实redundant cost
0.29638/0.12444。谱误差没有同等幅度下降，不能混用两种误差口径。

- 主图：[标量A](../local_runs/manuscript-three-groups-20261027/report/figure3_npg_scalar.png)、[稠密A](../local_runs/manuscript-three-groups-20261027/report/figure3_npg_dense.png)。
- [共享blocks机制表](../local_runs/manuscript-three-groups-20261027/report/same_blocks_summary.csv)。

图注：上排为绝对gap对累计转移，下排为全24重复分母的稳定率。所有阶段均保留，
固定k在正式运行前指定，阴影为IQR。精确真值仅用于评价，不参与更新。

## 验证、费用与复现

真实DARE/Lyapunov方程用于评价；正式数值分解残差见summary。
预检中批量与逐步pulse模拟误差至多5.7e-14，冗余代价恒等式残差至多2.6e-15。
全部576个原始NPZ哈希、576个JSON的源码/配置身份、首阶段配对一致性通过。
32个本地报告文件逐SHA256核对通过，10张PNG已逐图检查；同目录同时保留SVG。

预检20312823、正式数组20312937、报告20313020的26个实际分配全部COMPLETED。
实测elapsed×AllocCPUS合计1.020278核时，各allocation的billing=1；
不把该数冒充AMS已经结算的账户总消耗。请求上限合计3.5333核时，低于整轮12核时上限。
既有作业和现有SSH/PuTTY主连接未改动。

完整原始结果主存储：`/scratch/user/changze/lqr_experiments/results/manuscript-three-groups-20261027`。
冻结源码：同级`releases/manuscript-three-groups-20261027`。
本地仅取回报告、配置和收据，不下载全量轨迹。

- [冻结协议](MANUSCRIPT_THREE_GROUPS_PROTOCOL_20261027.md)、[配置](../configs/manuscript_three_groups_20261027.json)、[学习源码](../scripts/manuscript_three_groups.py)、[报告源码](../scripts/manuscript_three_groups_report.py)。
- [完整数值摘要](../local_runs/manuscript-three-groups-20261027/report/findings.md)、[逐输出CSV](../local_runs/manuscript-three-groups-20261027/report/all_records.csv)、[全分母统计](../local_runs/manuscript-three-groups-20261027/report/aggregate.csv)。
- [实际费用收据](../receipts/manuscript-three-groups-20261027-complete.json)、[本地校验](../receipts/manuscript-three-groups-20261027-local-verification.json)。

输入说明：指定名称main(2).pdf未在本机找到；实际核对桌面main.pdf的式(10)至(12)，
其算法与用户给定设计一致。文件哈希及映射记录于input收据；没有修改论文正文。
