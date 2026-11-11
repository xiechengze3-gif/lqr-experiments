# 三组主实验：冻结协议（2026-10-27）

本轮直接实现用户指定的 exact-rank CE、approximate-rank/adaptive CE 和单轨迹 NPG。
旧实验不混入新实验的统计分母。正式结果无论正负均报告，失败不删除。

## 系统与重复

统一 u=-Kx、Q=R=W=I、K0=0、m=n、每坐标探索方差1。
两类 A：0.5I，以及0.5O，其中 O 为独立于 B 的随机正交稠密矩阵。
因此两族都满足 ||A||=0.5，初始化稳定；不使用 Kstar 设计初始化。
B=U diag(s)V'，U/V 独立随机正交，学习器不接触真实子空间。
正式系统种子101/102/103，每系统采样100..107，共24重复。
标量 A 的不同旋转系统动力学等价；不能把24重复称为24种系统难度。

CE exact：n=12/24/48/96，r=2，s=(1,1,0,...,0)。
每轨迹只采一次连续探索数据，各前缀只拟合一次完整 Ahat/Bhat；dense、
oracle-rank truncated Bhat CE、adaptive CE 共享拟合。N/(n+m)=4/8/16/32/64/128/256。
所有前缀另计144 burn transitions。跨维度主比较固定 N/(n+m)=64，另给原始N曲线。

CE approximate：n=16，谱一为(1,1,.05,...,.05)，谱二为 .7^j (j=0..15)。
全部奇异值非零。N=256/512/1024/2048/4096/16384/65536；扫描
k=0/1/2/3/4/6/8/12/16，k16就是dense。同一前缀共享拟合。
adaptive 使用 t=||Bhat_first_half-Bhat_second_half||op/2，保留大于t的奇异值。
常数1在正式数据生成前固定，来自既有独立经验；不按本轮真值调参。
这是经验噪声代理，不声称已验证有限样本置信半径。真实cost最优k只能称oracle诊断。
保存 tau_k^2 与 k(n+m)/N+tau_k^2；后者只是未标定上界形状，不要求等于实际gap。

NPG：n=12，以上两类 A，exact / 两段满秩谱 / 平滑满秩谱。
dense 与固定秩截断各自一条连续轨迹，以相同外生噪声种子配对；不重置状态。
exact及两段谱固定k2，平滑谱固定k4，均提前指定。
使用正文 pulse/adjacent-return Stein 回归，保留已知 RK 项，更新
K_next=K-(RK+T_k(Zhat))/9。H=12，每阶段先12个pulse burn blocks，
再1个baseline和N个回归blocks。48阶段，N=2048/8192/32768/131072各12阶段。
累计M包括全部burn、baseline、回归。每方法预算完全相同。
保存第一阶段共享数据上的截断前后谱/Frobenius误差和下一步冗余代价，
该诊断不额外采样、不参与更新选择。无adaptive NPG或PI扩展。
步长对应统一供应的上界p0=4；本系统实际p0=4/3，满足该上界。

## 评价与失败

真实系统仅由模拟器和离线评价器访问；通过真实Lyapunov方程评价J，DARE求Jstar。
绝对gap为主，初始gap归一化为附加列。exact的真实投影仅用于诊断
J(K)-J(Pi_R K)，并独立核对其等于null gain在真实状态协方差下的代价。
approx满秩没有真实无效方向，不用人为head投影冒充redundant cost。
失败含DARE、回归、非有限数值和rho>=1。actor失稳后停止采样，未来预算仍计失败。
报告全分母稳定率、全分母成功率、稳定子集gap及失败按无穷大计的中位数。
记录所有计划输出、实际采集与分配采集数；CE共享前缀不重复计采样。
跨维度收益用配对比较；系统/采样两层bootstrap只作经验区间，不拟合复杂度定理。

## 计算与存储

仅在Grace真实Slurm计算节点执行模拟、数值核验和报告。
本地E盘保留源码、冻结配置、收据和小型图表；完整结果保存在Grace。
不改变已有作业或PuTTY/SSH主连接。
先用单核、2GiB、最多10分钟做最大n96 CE及完整NPG benchmark和数值恒等式核验；
根据实测计算整批成本，整轮硬上限12 allocated core-hours，含预检/报告/预留。
正式网格24个种子bundle，最多12并发；每bundle8条exact CE、4条approx CE、
12条actor，共576条采集轨迹。学习失败不自动重跑，执行超时不自动重放。
明确配置远端TMPDIR/XDG/Numba/Matplotlib缓存到本项目scratch；无大型C盘输出。
