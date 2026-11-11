# 最终 E1–E3 实验结果（2026-10-24）

结论：保留“精度决定有效截断阶数”的叙事，但不能把“经验NPG阈值始终贴住下包络”写成已验证结果。
严格低秩的冗余负担、PI截断收益和冗余方向鲁棒性都有清楚的正结果；NPG中高预算的秩扫描
出现内点最低值并随预算右移，但最高预算的最低点很浅。冻结NPG阈值明显过于保守。

已有实验的覆盖与缺口见[逐项覆盖审计](FINAL_STORY_EXISTING_COVERAGE_20261024.md)。旧n30冗余
实验已能支持收益，但没有PI，且大m失稳、截断也恶化；旧近似秩/自适应结果没有直接回答
同一满秩实例内的k扫描与独立标定后的交叉。因此本轮新增受控实验，不把旧结果拼成新主图。

## 设计、完成范围和预算

- 全部正式任务1560/1560，24个单核Slurm分片均COMPLETED。
- 完整actor轨迹1440条；389条失稳，全部来自E2的两个低预算，保留在全部分母中。
  E1的384条actor轨迹全部稳定；E2两个高预算的全部方法也都稳定。
- CE共120条数据采集轨迹、2088个相关的前缀/后处理输出，全部稳定；2088不是独立seed数。
- 每个正式单元24个重复=3个隐藏旋转实例×8个采样seed；旋转实例动力学等价，不能称作
  24种不同难度的系统。全程n=12，m≤n，无m≫n或弱方向分离实验。
- E1每臂11,805,696次转移，NPG64次更新、PI8次完整greedy更新；包含全部burn与baseline。
  E1 CE主点8192条回归转移+132 burn=8324。正式实际总采样20,446,345,632次转移。
  加上独立标定和预检benchmark，本轮采集总计21,242,141,092次转移；精确population与E3评价不增加训练采样。
- E2 NPG四个分配预算746,496 / 2,958,336 / 11,805,696 / 47,195,136；失稳提前停止，
  逐轨迹actual与assigned分开保存。CE使用512/2048/8192/32768/131072回归前缀，各加132 burn。
- 阈值在系统9001/9002、采样900/901上按预定规则独立标定，随后冻结NPG c=2、CE c=1。
  正式系统101–103、采样100–107未参与选择。未按测试结果重新调参、选择最佳迭代或恢复失稳策略。

E1用A=.5I、rank2 B的补零输入族，K0为范数.25的纯null rank1策略；各m的P0/Pstar/初始gap
通过数值不变量检查，实际p0=1.4166667，J0=16.0833333，Jstar=15.5988978。
所有m的 ||Pstar Fstar||_F²=4.5854934，敏感度stable rank=10.31736，不退化。
E2使用A=.7I、满秩B的奇异值.6^j、j=0..11，K0=0；只在同一实例内比较k。
共同供应的p0上界为4，NPG步长1/9；H=12，每阶段burn132。

不同actor分叉后有各自连续状态，配对的是外生创新，不能说整条学习使用相同观测数据。
CE后处理及单步counterfactual确实共享同一批数据。学习器不读取真实子空间，真实几何仅离线评价。

## E1：省下的冗余负担随m-r增加

下列为24重复的最终绝对gap中位数，全部稳定。

|m-r|NPG dense|NPG truncated|PI dense|PI truncated|
|---:|---:|---:|---:|---:|
|1|.02671|.02308|.06975|.03430|
|4|.04959|.03821|.19040|.03634|
|7|.07807|.04838|.27988|.03625|
|10|.11096|.06340|.36836|.03463|

PI的截断曲线近似持平，dense明显增加；NPG也省下越来越多gap，但截断曲线本身仍增加。
这支持冗余负担与截断收益，不支持“NPG truncated必须完全水平”。理论充分上界本身仍含n+m。

同一OLS拟合的CE真实冗余代价中位数：

|m-r|Dense CE|Truncated CE|
|---:|---:|---:|
|1|.0007356|.00002061|
|4|.0030563|.00006805|
|7|.0051888|.00011920|
|10|.0073357|.00018644|

Dense几乎随冗余维数线性增加。截断显著压低该项，但不为0；只有图上明确标为oracle的真实
子空间投影才为0。这与24 October技术报告Section7的陈述一致。不能把估计空间当成真实空间。

## E2：有效秩有证据，NPG自动阈值没有通过

失败按无穷大计入中位数。图中缺失的有限点表示至少一半失败，不表示未测或误差为0。

|NPG分配转移|观测最佳k|最低gap|固定k2|冻结阈值|Dense|
|---:|---:|---:|---:|---:|---:|
|746,496|0|1.69050|失稳24/24|1.69050|失稳24/24|
|2,958,336|1|.84330|.92131（失稳10/24）|1.69050|失稳24/24|
|11,805,696|4|.28033|.35052|1.54309|.32474|
|47,195,136|6|.07492|.23542|.87476|.07661|

中高预算的最低点从k4移到k6，符合精度提高需要保留更多方向的叙事。高预算k6与dense之差
很小，相比seed IQR不宜夸大；k4的U形更明显。固定k2在更高预算仍有较大残差。
最低预算的所有非零固定k均失稳；第二档k3失稳19/24、k≥4全失稳，不能把这两档称为
全部稳定的干净U形。

**冻结NPG阈值失败于“贴包络”这个经验要求。** 独立标定时小阈值低预算失稳较多，预定失败
惩罚使c2胜出；它在正式测试中稳定，却过度截断。不能看到这个结果后在正式数据上改选c.5/1。
这是该经验split代理与完整NPG协议的负结果，不是Corollary1的反例：代理没有被证明是总谱
置信半径，而且推论给单步误差oracle界，不保证最终策略始终贴住经验包络。

直接将dense末阶段实际raw谱误差平方代入k*a²+tau_k²时，两档诊断最优k是1/2，实际代价
最优为4/6；因此本轮没有验证该无额外标定的量能精确预测最优k。它只是保守上界形式，不能
忽略系统常数、阻尼/噪声平均和瞬态而当作数值选择器。

CE的完整k扫描和冻结阈值曲线另存附图；全部24重复、所有前缀/阶数均稳定。

|CE总转移|最佳固定k|最佳固定k的gap|阈值gap|阈值保留秩中位数|固定k2 gap|Dense gap|
|---:|---:|---:|---:|---:|---:|---:|
|644|3|.43032|.42438|3|.62721|.71326|
|2180|5|.13870|.14739|5|.54341|.18783|
|8324|8|.04361|.04422|6|.52226|.04626|
|32900|12|.01114|.01303|7|.51648|.01114|
|131204|12|.002929|.003778|8.5|.51525|.002929|

CE有清楚的bias/variance tradeoff和随预算右移；固定k2在约.515处被截断模型偏差限制，
阈值曲线较接近固定k中位数包络。Adaptive逐实例选择k，可低于“各固定k总体中位数的最小值”，
这不矛盾。最高档阈值仍略差于dense，不能称为逐点最优或已验证理论置信半径。

无噪声NPG参考另揭示：固定k1/k2在长迭代中会循环，不能把它们称为已收敛的唯一population
floor；保存了第64/256/512/1024步、策略变化和末64步gap范围。k≥3的参考收敛至对应截断
模型的附近，dense参考的残差约1.3e-9，说明采样高预算gap并非主要由外层未收敛造成。
NPG阈值正式末端保留秩中位数在四档都是0，最高档个别重复保留至2；这直接解释了过度截断。

## E3：同一已学策略对名义冗余方向的扰动更稳

只用E1 m12策略。每臂24条策略×10个独立固定方向=240次相关评价；Delta B Pi=0、
operator norm=delta，所有方法共享方向。相对变化=(Jpert-Jnom)/Jnom；改变系统后直接求
Lyapunov代价，允许负变化，不拿名义Jstar作扰动系统的下界。新增训练/部署转移均为0。

|方法|delta8：稳定子集代价变化中位数|delta8：失稳/240|delta16：失稳/240|
|---|---:|---:|---:|
|NPG dense|+35.82%|6|127|
|NPG truncated|+11.07%|0|25|
|PI dense|+256.07%|119|239|
|PI truncated|+0.695%|0|0|

大幅扰动下不能只比较幸存者代价；全分母失稳率才是主要结果。截断PI最清楚，NPG也更稳。
这仅针对消去名义有效空间的扰动，不推广为任意系统扰动的保证或NPG/PI的一般优劣排序。

## 论文采用建议

1. 图1可直接采用：1a完整NPG/PI冗余扫描，1b真实CE冗余代价；正文写NPG增长较缓、PI近似持平。
2. 保留有效秩主线，用图2a的同实例k扫描和CE附图支撑。不要写所有NPG预算都有U形，或
   观测最优阶数精确等于一个未标定常数的上界最优解。
3. 当前NPG图2b应作为明确负结果。若只允许两张主图，可考虑用CE交叉作为2b，并保留
   NPG阈值负结果在正文一句/附录；不能将其隐藏或宣称自动NPG已获验证。
4. E3用上表的小表。历史100d/500d、一般Q/R和不稳定开环结果作为外部适用性补充，不做跨系统预算比伪装。

所有实例/阶数的tau_k²、beta_k、敏感度、p0、spectrum与尾部rank均在CSV。k_epsilon表
预先固定操作性c_eff=1，仅为尾部尺度演示；技术报告的证书常数未数值化，不能把它称为
已认证的理论k_epsilon。完整协议及解读边界分别见
[协议](FINAL_STORY_PROTOCOL_20261024.md)、[解读边界](FINAL_STORY_INTERPRETATION_NOTES_20261024.md)。

## 交付与验证

最终结果位于 [E盘结果目录](E:/ChatGPT/Results/LQR_experiments/final-story-20261024)。
已完成核心统计、两张主图、CE附图、population参考、E3、全量归档及本地核验。
归档SHA256为 `0d338e3f48b4f2e3e895fb3c0ef64d7c15046fd18fd596ad52542c1238ebc6ec`；
[本地核验](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/local_verification.json)对3271个文件全部PASS。
Slurm实分配3.351111核时，包含预检、标定、冻结、正式学习、只读进度及全部报告修正；
这是本人作业elapsed×AllocCPUS，所有allocation billing=1，不冒充AMS已结算总额。
[最终结算](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/final-story-20261024-final-accounting.json)
保留每项作业和当时myproject快照；没有遗留运行作业。
报告阶段的空集合NaN、扰动后名义gap检查和导出路径常量错误均保留日志并仅修复后处理；
学习轨迹未重跑、阈值未改、失败未删。已有9张数值CSV用冻结哈希验证重生成逐字节一致。

- [图1 PNG](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/report/figure1_strict_rank.png) / [SVG](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/report/figure1_strict_rank.svg)
- [图2 NPG PNG](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/report/figure2_effective_rank.png) / [SVG](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/report/figure2_effective_rank.svg)
- [CE近似秩附图 PNG](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/report/figureS1_ce_effective_rank.png) / [SVG](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/report/figureS1_ce_effective_rank.svg)
- [E3小表](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/report/e3_small_table.csv)
- [每实例/每k的尾部与证书](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/report/system_tails_certificates.csv)
- [操作性k_epsilon表](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/report/effective_ranks_operational_c1.csv)
- [逐actor终点/失败/预算](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/report/actor_endpoints.csv)
- [全部采集计数](E:/ChatGPT/Results/LQR_experiments/final-story-20261024/report/all_new_sampling_accounting.csv)
- [完整归档](E:/ChatGPT/Results/LQR_experiments/final-story-20261024.tar.gz)

正式学习源码保持冻结。当前正确的后处理入口是`final_story_finalize.py`，使用`final_story_report_v4.py`
和独立的`final_story_robustness.py`；不使用冻结学习模块中历史的robustness CLI。正常报告使用
`slurm/final_story_review.sbatch report`，已有核心表的核验/补充导出使用`slurm/final_story_finish.sbatch report`。
两者均需真实Slurm分配，不伪造job id。图注与小表文字见[可用图注](FINAL_STORY_FIGURE_CAPTIONS_20261024.md)。
