主文的正面证据优先用新X1-CE、X2-CE和X3-CE。所有新实验使用独立生成、开环不稳定的A/B，
以及不调用Q/R、最优解或成本的稳定化初始化。NPG的弱结果和负结果应在正文明确说明，
细表可放附录；不能为维持正面叙述而删除这些结果。未修改任何论文TeX。

| 实验 | 建议位置 | 证据边界 |
|---|---|---|
| X1-CE gap和逐输出ND/v* | 主图(a)/(b)候选 | 主点N8192全部稳定；m=r是独立零null基线，非零null匹配仅对m>r |
| X2-CE维数/秩表 | 表1候选 | 比值限同系统有限配对，同时列失败人数；39/56项精度右删失，不能外推 |
| X3-CE固定k、平坦谱与自适应曲线 | 主图(c)候选 | 包络是事后诊断，阶数并非严格单调；论文阈值两层谱负结果保留 |
| X1/X2-NPG及P1/P2 | 机制图/正文限制说明，完整细表附录 | D下降不等于总gap改善，原整体配对CI包含1 |
| X3-NPG | 负结果/负对照，正文诚实说明，完整网格附录 | 36个CI中31个偏向dense、5个含1；不能作为普遍截断收益的主证据 |
| X1-PI v4 | 附录诊断 | dense116/288、截断77/288终点失败；不是正文NPG，也不是LSTD-PI |
| X4 | 附录鲁棒性诊断 | 0训练，10方向不是额外独立系统；扰动后gap并非截断处处更优 |
| 旧nominal-burn NPG、LSTD-PI | 版本参考/附录 | burn或估计器不同，不能用作正文Stein-NPG主验证 |
| 旧100维matched-gap、高秩两系统CE | 补充对照 | Kstar邻域或联合设计初始化、系统数小；不替代新F5主证据 |

三个风险的回答：

1. **失稳主要在哪边，必须分版本和算法回答。** 新X1/X2/X3-NPG总共2144条路径全部稳定；
   新X1-PI为dense116/288、截断77/288失败。新X2-CE为dense771/4704、截断329/4704失败输出。
   历史严格低秩NPG是dense163/288、截断65/288；旧100维原排程200条全失败与matched-gap
   300条全稳定是不同实验。截断降低部分设置的失败率，但不能说所有设置都如此。
2. **建议图(a)、图(b)、表1统一使用正文CE。** 单连续轨迹、512步带高斯探索burn-in、
   原坐标联合OLS，同一完整拟合供dense与截断，仅截断Bhat。X3同时给冻结C5论文阈值和
   split经验代理，不能混成一种方法。新NPG全部使用Stein相邻pulse-return差、H32、16个
   pulse burn blocks和baseline，保留RK、仅截断Zhat，eta/T和增长batch在正式前冻结。
   PI v4另列，未以LSTD critic冒充正文算法。
3. **NPG只作固定预算经验比较。** 同时提供absolute gap及逐输出初始gap归一化的relative gap，
   不声称已经验证指定epsilon成功率或样本复杂度。X3仅有三个4倍batch档，也不能用于要求
   sqrt(2)网格的epsilon首达预算。稳定不等于达到高精度。

X3-NPG最重要的负结果：平滑谱和平坦谱在每档都选dense；两层谱绝对gap包络为4→12→12，
相对gap包络为6→12→12。最低预算k4绝对gap中位数.130425略低于dense.140630，但逐对比值
1.02154的95%区间[.942661,1.14822]包含1。提高预算并未转成截断的总体优势。

末阶段两层谱k2自己的估计误差中位数1.70801/.740596/.376743小于dense的
2.14140/1.10263/.532519；在同一个dense策略和同一raw估计上离线截断也降低该误差，
配对范数比1.406/1.461/1.523的区间均在1以上。但实际dense/k2终点gap比为
.8298/.5870/.4435，后两档明确偏向dense。这说明瞬时无权Frobenius误差不能直接代表终点控制代价。
截断偏差、代价方向权重、策略依赖目标与完整优化路径都可能影响结果，本诊断没有隔离各自因果贡献。
满秩B不能套用top-2零空间冗余恒等式，不能把“子空间对齐不好”当成唯一已证实原因。

关于Theorem3，严谨表述是：实用有限预算没有逐项认证高概率镇定结论所需的全部充分常数和
路径小误差条件。不能未经数值化便写“预算低于理论常数”，也不能把这些经验失败称为满足
全部定理条件后的反例。新NPG全路径稳定也不等于认证了定理全部路径区域。

可供正文使用的英文说明：

> Schedules were frozen using disjoint pilot systems and a dense-arm calibration rule.
> These practical budgets do not numerically certify every sufficient constant or
> pathwise error condition in Theorem 3. We retain all planned repeats and assign
> infinite gap to failed outputs. NPG results describe fixed-budget comparisons,
> without an accuracy-attainment or sample-complexity claim.

所有主图均给稳定/全分母；有限配对数与失败率同时提供。X3-CE稳定区域图的n32两层谱曾按显示
规则排除最高两个前缀，完整网格和负结果不得删除。固定k0的3456个失败单列诊断，adaptive
实际选择k0仍属于学习方法失败；自适应保留秩一律用v5真实分布，不能引用旧aggregate的首样本k。

数值入口：各X的`report-ce/`或`report-actors/`；X3自适应解释用v4和v5，NPG末阶段用
`report-npg-last-estimator-v1/`；P1/P2用`analysis-P1-P2-v1/`和`analysis-P1-P2-tables-v2/`。
旧四组的逐版本审核保持在上层`AUDIT.md`，新旧数据不合并估计。
