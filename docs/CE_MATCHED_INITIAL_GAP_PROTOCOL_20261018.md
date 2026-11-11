# CE：匹配初始 optimality gap 的跨 rank 对照

预先声明于2026-10-18；数值验证与采样尚未完成。本轮先研究CE，不将PI/NPG扩展混入新扫描。新旧实验结果分别保存。

## 问题与主比较

检验在相同初始 optimality gap、相同 relative target 下，low rank + truncated CE 是否比 full rank + dense CE 需要更少的 primitive transitions。主比较为rank2 truncated与rank100 dense，rank8/32/64作为完整rank切片；每个rank仍同时计算dense与truncated，避免把系统变化与后处理收益混为一谈。

固定n=m=100、Q=R=W=I，ranks=2/8/32/64/100。复用上一轮原始NPZ字节中的A、B_r、U/V及最优解，A/B和成本矩阵不重新生成。相对于上一轮，变化的是初始策略及独立的新采样随机源。

## 匹配初始化

一次生成独立于真实子空间的满秩Haar正交矩阵D，所有rank共用。设

`K0_r = Kstar_r + alpha_r D`，

在从最优策略出发的稳定射线上用二分法求第一个正alpha，使

`J_r(K0_r)-Jstar_r = Delta0 = 1`。

不通过单独往无效动作空间添加损失来补齐gap。Kstar、D、alpha仅用于私有系统初始化；学习代码不接收Kstar或真实子空间。CE核心仍是既有原坐标完整OLS估计A/B，保留同一Ahat，仅对Bhat作rank-r SVD后求DARE。公开给采样器的初始增益为K0_r，必须验证其满秩，避免提供带有精确rank-r行空间的初始增益。

准备阶段逐rank验证真实gap与performance-difference identity各自距离1小于1e-10，rho(A-BK0)<1，Lyapunov证书残差小于1e-10，并检查从Kstar至K0的稳定性网格。A/B/Q/R/W与冻结输入逐元素一致。J0、P0、初始闭环和探索状态协方差允许随rank变化，全部报告；不再声称共同initial value或共同F0。

## 采样与预算

CE从匹配后的K0_r收集连续轨迹，行为`u=-K0_r x+e`，e各坐标标准差sigma=2，过程噪声W=I；每条轨迹只做一次256-transition nominal burn，全部计入预算。初始状态零，K0_r在整个OLS数据收集期间固定。外生过程噪声和探索噪声分别用独立随机流，种子不含rank或算法；分块不改变两个随机流的行顺序。不同rank不要求状态轨迹相同。

同rank两种后处理共享全部原始数据、Ahat和Bhat；full rank时截断为恒等映射，增益必须逐元素相同。所有rank使用同一采样规则，不用真实代价选择更新、真实子空间或秩以外的真值信息。

独立pilot种子0–4，粗OLS预算512×2^k直到131072。正式新种子200–229，均不与旧正式100–129混用；预先固定21个OLS前缀：512/1024/1536/2048/3072/4096/5120/6144/8192/10240/12288/14336/16384/20480/24576/28672/32768/49152/65536/98304/131072。总预算另加256 burn。pilot核实达标区间与性能后才提交正式数组；正式不按rank调超参数，也不按结果挑种子。

主relative target为0.1，敏感性为0.05。因为Delta0固定为1，它们同时对应共同absolute gap 0.1、0.05。Nhat为最小已测预算中至少27/30输出在真实系统稳定且达标的预算。OLS/Riccati失败及失稳保留在分母；最大预算未达标标记not reached。所有轨迹跑完整预算，不因真实代价达标提前停止。

## 分析与审计

报告各方法成功率及Wilson95%区间、离散Nhat及2,000次配对种子曲线bootstrap区间。主跨rank收益定义为`Nhat(rank100,dense)/Nhat(rank r,truncated)`，大于1表示low rank + truncation更省样本；删失不强行赋有限比值。相同预算下另比较两者的absolute/relative gap以及配对bootstrap区间；Delta0相同使二者的跨rank比较具有相同精度口径。

保存所有策略、原始评价、完整最终OLS充分统计量、最终Ahat/Bhat、随机状态与checkpoint。独立重算所有保存策略的真实代价，另用performance-difference identity核对gap；检查full rank全部预算的两方法一致。准备阶段还进行无噪声OLS恢复和低/满秩两次checkpoint中断恢复测试。

匹配初始gap不能同时匹配探索状态分布或控制能力，K0还由真最优策略加随机扰动构造。因此本轮检验的是这一明确系统族上的empirical observation，不识别纯估计器rank因果效应，也不保证低rank一定取胜。

## 运行资源与存储

Grace当前账户132685389143（2027财年），提交前myproject显示Used & Pending11265.37、余额8734.63；该快照不是本轮实际消耗。数值工作在真实Slurm计算节点运行，复用现有Python环境，不安装依赖。1CPU、2GB每任务，线程1；上限8核时，自动重试0。5分钟验证、25个pilot任务和150个正式任务各最多2分钟、5分钟pilot报告、15分钟正式审计报告及10分钟归档的最坏初始申请合计6.416667核时，另留至多1核时人工断点恢复，总额不超过8。正式提交前以最大预算benchmark核实时间与内存依据。

远端输出/缓存/临时目录分别是`/scratch/user/changze/lqr_experiments/{results,cache,tmp}/ce-matched-initial-gap-20261018`。本机结果为`E:\ChatGPT\Results\LQR_experiments\ce-matched-initial-gap-20261018`，本机临时和缓存使用E盘。冻结包、配置、源码哈希、作业日志、实际sacct核时和归档SHA256均保留。
