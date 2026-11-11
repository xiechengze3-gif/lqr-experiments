# Project 2：逐组实验公平性审核

审核日期：2026-10-22。**核心的同系统 dense／截断收益成立；不能把所有跨秩、跨算法数字都解释成截断本身的收益。** 新版 v4 PI、100 维 NPG 和完整原坐标 LSTD PI 的主要比较，初始化、采样规则、更新次数和评价规则匹配。CE 也有同系统样本节省，毋须依赖跨系统的最大倍率来建立论点。

本次重新读取实现、冻结配置、逐轨迹 JSON 和预算表。自动检查覆盖 72 条新 PI 轨迹、300 份 matched-gap NPG／PI 正式结果、21,960 个不同的一步输出，以及 30／100 维动作冗余的全部 400 条轨迹。历史系列逐组对照其协议、实现及已保存的审计；表中明确注明哪些只是诊断、复用或未完成系列。数值一致性 PASS 与“比较是否回答了相同问题”分别判断。

另发现此前汇总遗漏的完整负结果：**100 维动作冗余实验的 200 条轨迹全部失稳；采样已完成，原目录没有汇总 report。** 本次已从全部原始结果补出统计表。这不是一个待完成的正结果。

**另一个实质结论：adaptive 的经验 c1 阈值有效改善性能，但没有通过真实联合误差的覆盖检查。** 中央 N524288 为 0/160 覆盖，不能将其写成已经实测成立的高概率噪声证书。

## 最值得保留的公平对照

| 比较 | 匹配了什么 | 结果 | 审核结论 |
|---|---|---|---|
| v4 PI，50d/r4，dense／known／adaptive | 同一系统与 K0；相同 H16、sigma1、burn512、6 次完整 greedy 更新；最高档三臂实际均使用 50,334,816 transitions | 相对 gap 经验中位数 .963061／.031782／.055335；达标 0/8、8/8、8/8 | **公平，适合作为 v4 主图。** 组中位数比约 30.3／17.4；逐系统配对比的常规中位数为 32.81／18.01，8 个系统全部受益 |
| matched-gap NPG，100d/r2 | 同一系统和 K0；统一 eta=.05、H4、sigma2、44 次更新、共同 batch 排程；30 个配对采样 seeds | 最大共同预算 gap .132158→.017392，组中位数比 7.60，配对比中位数 7.58 | **公平，适合作为 NPG 主图。** 表示同预算精度收益 |
| matched-gap 原坐标 LSTD PI，100d/r2 | 同系统、同初始策略、同四轮采样；完整 20,100 系数 critic、rtol=1e-6、相同两次求解尝试 | 最大共同预算 gap .172221→.001904，组中位数比 90.44 | **公平，适合作为 LSTD PI 主图。** 这是 [G,C] 版本，不替代 v4 对应实验 |
| matched-gap CE，100d/r2 | 相同连续数据与完整联合 OLS；相同 Ahat，只截断 Bhat | target=.1 的同 rank dense／trunc 预算 14,592／3,328，4.38 倍；同最大预算 gap .009340／.001752 | **公平。** 4.38 倍在这里也能由同系统比较得到 |
| 原 CE500 族，r2，含 rank4 扩展的正式表 | 同系统、同 K0、同 OLS 前缀；只改变估计后的 rank 截断 | target=.1 同 rank dense／trunc 的有效样本前缀预算 327,936／14,592，22.47 倍 | **公平。** 倍率按该族、该离散网格及有效前缀口径报告；不与等模态族混合 |
| 新增固定策略同数据一步 PI／NPG | 同一个 K、同一份 Ghat／Zhat、相同更新步；全部方法共享数据 | 高预算中央组 PI 成本 17.319／.860／1.504，NPG .060664／.024101；所有输出 160/160 稳定 | **公平的机制实验。** 这里 K=Kstar；160 次是 4 系统×40 采样重复，不是从未知最优策略开始的完整学习 |

上述 PI 与 NPG 倍率是 gap 的改善，CE 的预算倍率是达到固定精度所需的已测预算比，二者不互换。

## 每组实验的审核结果

“公平”表示适合检验该组声明的问题。known-rank 参考明确获得整数 r；adaptive 不获得真实 r。固定相同超参数能隔离后处理的作用，但不表示已对 dense 做过独立的最优调参。下表以实验系列为单位逐一列出；同一数据的后续图、诊断、重放不重复记成独立实验。

| 编号与系列 | 实际对照及证据 | 公平性判断 | 推荐采用的结论 |
|---|---|---|---|
| F01 16／32d 最早 pilot 与两次 follow-up，176 配置 | K0=0、独立 B 奇异基；CE／固定 K critic 同数据，actor 配对随机源；失败全保留。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/PILOT_FINDINGS_20261007.md) | **组内公平。** 两系统×两采样重复；首次与持续达标定义不同 | CE 有预算收益；NPG 有末端／持续表现收益。不能把两臂同在第 5 步首次达标写成首次样本节省 |
| F02 原 dense 家族及早期 NPG／PG／Direct PI | 712 配置主研究中的原 stabilizer 家族；同系统后处理匹配，但 K0 的前 r 个奇异向量给出真实动作空间。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/DENSE_STUDY_FINDINGS_20261007.md) | **同系统作用对照公平；未知几何 benchmark 不合格。** 原 PG 还包含协方差估计与方向归一化 | 保留机制和早期负结果；不作为无子空间线索或 vanilla PG 的主证据 |
| F03 isotropic stabilizer 修正后的 CE／critic／actor | K0 全部奇异值 .35，无法靠主奇异子空间选出真实 r 维方向；4 个系统，dense／trunc 同数据或配对创新。[控制说明](E:/ChatGPT/Projects/LQR_experiments/docs/ISOTROPIC_STABILIZER_CONTROL.md) | **公平，未知动作空间的主要证据。** 改 n／r 时物理系统也变化 | CE 的 n、r、N 经验标度与同系统估计误差收益；拟合窗口 r/n≤.2，不能丢掉窗口外结果后声称全域规律 |
| F04 64 个收敛 population 尾部配置 | 同一 n/r/seed 内保持 A/Q/R/K0，改变尾部；每个算法运行到更新范数收敛而非任取固定步数。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/DENSE_STUDY_FINDINGS_20261007.md) | **公平的偏差机制对照。** 使用真实模型，原族初始化有结构信息 | 平方 Frobenius 尾能量对应收敛残差；不是可实施方法的采样效率比较 |
| F05 NPG precision，54 配置 | 6 次历史重放、44 固定策略校准、4 精度干预；同起点、步长、更新次数，batch 不同。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/NPG_PRECISION_FINDINGS_20261007.md) | **精度机制公平；4 倍 batch 干预不是等样本预算。** exact critic 是 oracle | 可以说 critic 精度限制表现；不能将 15.315→13.679 当作省样本证据 |
| F06 历史 CE／full-LSTD PI／NPG 联合扫描，324 配置 | 各路线内相同系统、排程、后处理；原 LSTD 完整 critic 采用可逆白化。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/CROSS_RANK_FINDINGS_20261008.md) | **算法内公平；跨算法不是完全配对。** CE／PI／NPG 的轮数、H、精度展示口径有差异 | 可作历史稳健性与尾部结果；不得改名为原坐标无白化 LSTD，或用不同 epsilon 的表给算法排名 |
| F07 PI／CE 子报告及旧图修订 | F06 的子集与绘图修正，没有新增独立系统。[子报告](E:/ChatGPT/Projects/LQR_experiments/docs/PI_CE_COMPLETE_FINDINGS_20261008.md) | **沿用 F06 的公平性；不是另一轮复现。** 当前源码已变更，须读冻结版本 | 与 F06 合并引用，避免双计实验数 |
| F08 NPG growing80 rank 扫描，24 配置／48 轨迹 | raw／trunc 同系统、相同 80 次日程、eta 与阶段随机源。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/NPG_RANK_FINDINGS_20261008.md) | **算法内公平。** 固定 r 改 n、固定 n 改 r 并不固定整套控制问题 | 展示同系统完整学习及持续达标；不能独立识别纯 rank 因果效应 |
| F09 NPG constant／growing 同总预算，32 轨迹 | 两日程均 128 次更新，block 数总和相同，burn／baseline 相同，组内步长一致。[实现](E:/ChatGPT/Projects/LQR_experiments/scripts/npg_epoch_budget.py:25)、[结果](E:/ChatGPT/Projects/LQR_experiments/docs/NPG_EPOCH_BUDGET_FINDINGS_20261008.md) | **公平，排程作用的直接对照。** 路径随日程变化是处理的结果 | 后期多分配数据可改善终点；已足够，不需拿不同总预算的长跑替代 |
| F10 NPG 12 排程／7 秩／4 系统，672 轨迹 | A/Q/R/K0 在同 seed 内固定，B 嵌套；两方法同一候选排程网格与固定 256 次输出，98 失稳保留。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/NPG_BUDGET_ORDER_FINDINGS_20261009.md) | **同 rank 公平；跨 rank 是系统能力变化对照。** 从 12 日程中选最小达标预算 | 用已测共同网格上的预算收益；不能称穷尽调参后的最优复杂度 |
| F11 NPG critic rank 与 log–log 再分析 | F10 的同一大预算日程，最后 16 次不同策略更新，先系统内平均，再汇总 4 系统。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/NPG_RANK_LOGLOG_FINDINGS_20261009.md) | **描述性诊断有效；不是独立固定 K 实验。** 0.991 是 critic 误差的 rank 斜率 | 与端到端预算约 .535 的斜率分开；不将 16 个阶段当独立 seed |
| F12 8d 未知秩三路线 pilot，240 轨迹＋960 固定策略输出 | 同数据估计、预设 c=.5/1/2，主版本 c=1；exact／weak／decay／flat 均保留。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/ADAPTIVE_RANK_FINDINGS_20261011.md) | **公平。** known-rank 获得 r，adaptive 不获得；split 阈值是经验代理 | CE／LSTD 存在实际收益及过截断反例；Direct dense 在该早期预算失稳，不据此排算法总榜 |
| F13 8d CE／LSTD／NPG 修正主比较与 NPG32 extension | 方法替换有单独版本；6 与 32 更新各自有共同 dense／trunc／adaptive 对照。[协议](E:/ChatGPT/Projects/LQR_experiments/docs/ADAPTIVE_CE_LSTD_NPG_PROTOCOL.md)、[汇总](E:/ChatGPT/Projects/LQR_experiments/docs/LQR_ALL_EXPERIMENTS_20261014.md) | **各版本内公平；版本间不能当等预算比较。** NPG c1 不一致改善 dense | 未知秩的可运行性和失败边界；不只挑 adaptive 有利谱 |
| F14 50d adaptive 四路线旧快照 | 同任务初始化和方法排程，但整批被后续协议替换；共同完成的 task0–3 只是一个系统的快照。[快照](E:/ChatGPT/Projects/LQR_experiments/docs/ADAPTIVE50_INTERIM_20261012.md) | **完整配对快照内可比；不能代表全计划。** LSTD 求解失败保留 | 作为原坐标求解困难与负结果，不作高维正式胜率证据 |
| F15 fixed-value／cumulative／relaxed-LSTD／growing-NPG 四版 | 先后改变 CE 累计方式、LSTD 容差、NPG 日程；有源 hash／重放／检查点记录。[协议](E:/ChatGPT/Projects/LQR_experiments/docs/FIXED_VALUE_PROTOCOL_20261012.md)、[修订](E:/ChatGPT/Projects/LQR_experiments/docs/GROWING_NPG_PROTOCOL_20261012.md) | **同版内才可比；整批未交付。** 不能把不同版的最好终点拼成同一对照 | 留作算法／数值诊断；不将计划 1200 轨迹写成完成量 |
| F16 历史 100d adaptive NPG 补充，18 新＋36 旧 | 每个 case 校验旧源和首步数值一致，保留同 K0、标量步长、H16、原 80／256 更新日程。[协议](E:/ChatGPT/Projects/LQR_experiments/docs/HISTORICAL_NPG100_ADAPTIVE_PROTOCOL_20261012.md) | **匹配的历史 baseline 复用公平；不是 54 条新实验。** 1 条 adaptive 失稳保留 | 说明高维 adaptive 有效性取决于谱／预算；不写普遍优于 dense |
| F17 旧 Direct-Stein damped PI，72 正式轨迹 | 8 个系统 101–108、eta=.25、8 更新、三共同预算；pilot 801／802 分离。[报告](E:/ChatGPT/Projects/LQR_experiments/docs/FINAL_ROUND_REPORT_20261014.md) | **公平。** 投影后 PSD 与阻尼更新是旧版定义 | 成熟学习收益的证据；须与完整 greedy 的 v4 分开命名 |
| F18 旧最终轮固定策略／horizon／forced-rank 诊断 | 同估计比较 known／adaptive，另含真实模型与 full-rank 强制 r4 负对照。[报告](E:/ChatGPT/Projects/LQR_experiments/docs/FINAL_ROUND_REPORT_20261014.md) | **公平的机制及反向对照。** 真实参数参考只作诊断 | 不适合低秩时会有偏差，阈值及 H 的作用有直接证据 |
| F19 rank／dimension 扩展，864 PI 轨迹 | 792 新＋72 复用；同 cell 三臂同预算；227 失稳＋2 数值失败保留；CE／NPG 每 cell 2 系统。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/ALIGNED_EXTENSION_FINDINGS_20261015.md) | **同 cell 公平；跨 rank 相对 g 的初始分母不同。** 已有共同绝对 epsilon 补表 | 采用低 rank 收益和 n100/r32 反例；不把 dense 随 r 的 g 下降纯归因于 rank |
| F20 n100 high-rank CE 粗网格 | r16/32/64/100，原两系统，dense／trunc 同前缀；新增与复用有记录。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/CE_HIGH_RANK_FINDINGS_20261015.md) | **公平；4 倍间隔太粗，不能给精确收益倍率。** | 作粗网格来源；最终倍率用 F21 |
| F21 high-rank CE precision zoom | 相同系统、相同轨迹前缀，180 个更密预算；旧前缀及满秩身份重现。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/CE_PRECISION_ZOOM_FINDINGS.md) | **公平；网格细化预先声明。** 是同一系统的精化，不是新增系统复现 | r16/32 的约 4 倍应改用 2.22／1.42 倍，r64 约 1.08 倍 |
| F22 high-rank adaptive CE zoom | 同 F21 设置与预算，冻结 split c1；known／adaptive 预算一致；8 个最小预算 adaptive 失稳保留。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/CE_ADAPTIVE_ZOOM_FINDINGS.md) | **公平。** 历史 baseline 逐前缀重放；样本规模仍为两系统 | 未知秩无需真 r 仍可保留该族的高 rank 收益 |
| F23 n30 动作冗余，200 轨迹 | n30/r4、m8–128；固定有效系统、BB'、初始 F/P/gap、null gain 范数；每格 20 配对 seeds。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/ACTUATION_REDUNDANCY_FINDINGS_20261016.md) | **公平，隔离冗余动作维数较好。** 固定每坐标探索，非固定总能量；低预算失败后实际用量不同 | m≤32 同预算改善，m64 稳定性收益；m128 有 6/20 截断失稳，不能只展示剩余 14 条 |
| F24 n100 动作冗余 follow-up，200 轨迹 | 同 F23 算法／排程，仅 n 改为 100；每个 m 内不变性已验证，100 份 paired 原始结果齐全。[协议](E:/ChatGPT/Projects/LQR_experiments/docs/ACTUATION_REDUNDANCY_N100_PROTOCOL_20261016.md) | **对照公平，结果全部失败。** 五个 m 两方法均 0/20 终点稳定；这轮没有跑通的高维正结果 | 必须列为高维早期预算失败；跨 n 不同物理系统，不能当同系统维数处理 |
| F25 原固定 100d rank sweep 的 CE／NPG | 同 A/K0/F0/P0、嵌套 B，30 正式采样 seeds；同 rank 两方法参数一致，共同绝对 epsilon。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/RANK_SWEEP100_FINDINGS_20261017.md) | **同 rank 公平；K0 的一个方向与真实空间对齐，且初始 gap 随 r 变。** | 同系统曲线有效；跨 rank 优势包含优化／初始差距变化，未知几何主证据用 F03 |
| F26 原 100d full-LSTD PI，30 seeds/rank | 完整原坐标 20100 系数、同 rtol／求解尝试／四档 batch；相同 K/x 时共享估计，之后配对随机源。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/RANK_SWEEP100_PI_FINDINGS_20261018.md) | **同 rank 公平。** 与旧白化 PI 不同；不将 actor 后处理叫作 critic 方程降维 | 可直接用于原坐标算法结果，跨 rank 解释沿用 F25 |
| F27 原 30-seed fixed-budget 再分析 | 原始 295 rank/budget 点、8850 配对观测；各算法使用各自最大预算。[脚本](E:/ChatGPT/Projects/LQR_experiments/scripts/rank_sweep100_fixed_budget_report.py) | **算法内公平；跨算法终点预算不同。** 无新增样本 | CE／NPG／PI 各自的 gap 改善倍率有效，不按这三个倍率排序算法 |
| F28 matched initial-gap CE100 | 五份系统各初始 gap=1；K0=Kstar+alpha D；dense／trunc 共享完整原始 OLS。[结果](E:/ChatGPT/Projects/LQR_experiments/docs/CE_MATCHED_INITIAL_GAP_FINDINGS_20261018.md) | **同系统公平；matched gap 没有匹配探索分布／控制曲率。** K0 满秩不等于没有子空间线索 | 同 r2 的 4.38 倍预算收益可直接用；跨 rank 表单独解释 |
| F29 matched-gap NPG100 | 与 F28 相同五份系统与 K0；30 新采样 seeds，所有 rank 共用 eta／H／batch／44 更新。[实现](E:/ChatGPT/Projects/LQR_experiments/scripts/rank_sweep100.py:177) | **同 rank 公平。** 不同算法并不共享 CE trajectory；dense 未独立调到最优 | r2 同预算 7.60 倍精度收益；跨 rank 的 8.24 倍预算比另列，不作纯截断倍率 |
| F30 matched-gap full-LSTD PI100 | 与 F28 相同系统文件；完整原坐标 critic、统一 rtol=1e-6、两尝试、四更新。[实现](E:/ChatGPT/Projects/LQR_experiments/scripts/rank_sweep100_pi.py:60) | **同 rank 公平。** full-rank 两臂逐阶段完全相同；运行资源与 NPG 不同 | r2 同预算 90.44 倍精度收益；不是与 v4／CE 等计算预算的排名 |
| F31 CE identification／known-A／同误差方向干预 | 同原始 Ahat/Bhat 替换单个输入；另以相同独立扰动方向跨 rank 评价。[审核](E:/ChatGPT/Projects/LQR_experiments/docs/CE_IDENTIFICATION_AUDIT_20261019.md) | **公平的局部机制实验。** true-A／true-B 对照拥有额外信息，仅作 oracle | A 估计限制同 rank CE 收益；跨 rank 的控制几何会削弱模型误差收益，不把误差收益等同控制收益 |
| F32 原 CE500 matched-gap 与 rank4 扩展 | 各 rank 内共享 OLS，rank4 补充保留旧系统／旧数据及 provenance。[同 rank 表](E:/ChatGPT/Projects/LQR_experiments/analysis/fairness-audit-20261022/CE_within_vs_cross_rank.csv) | **同 rank 公平；跨 rank 是不同 B／K0／控制问题。** 初始化携带显著子空间信息 | 同 r2 有 22.47 倍已测有效前缀预算收益；原族曲线与等模态、random-A 分开 |
| F33 CE500 等模态族 | 控制模态的系数统一，但 A=.45I+.75 U_r U_r' 随 r 变化，K0 也变化；同 rank 两方法共享数据。[构造](E:/ChatGPT/Projects/LQR_experiments/scripts/ce500_equal_modes.py:50) | **同 rank 公平；47.16 倍是跨系统预算比。** r2 最低正式预算已达标，dense 在该 r 网格内未达标 | 展示受控族的跨 rank 趋势；不能称“同系统截断省 47 倍”或 47 倍是精确最优复杂度 |
| F34 CE500 independent random-A | 同一满秩随机 A，独立 Haar B，A 跨 r 逐字节相同；每 rank 同数据 dense／trunc。[构造](E:/ChatGPT/Projects/LQR_experiments/scripts/ce500_random_a.py:32) | **同 rank 公平；跨 rank 比等模态控制更充分，但 B/K0/探索分布仍变化。** r2 dense 未跑到达标 | .1 的跨 rank 5.23 倍可用，不能改名为同 rank 的精确预算节省；用 review-v2 正式执行计数 |
| F35 新 v4 PI，72 正式轨迹 | 三臂仅后处理不同；先 PSD、[G+,Z] SVD、双侧压缩、完整 greedy，统一 H／burn／更新数。[实现](E:/ChatGPT/Projects/LQR_experiments/scripts/project2_overnight.py:78) | **公平。** 8 物理系统复用 F17、采样流新；低档是相同上限，高档为相同实际用量 | 作为新版直接主结果；不累计为又新增 8 系统，不称最优调参 dense 的普遍下界 |
| F36 新固定策略同数据一步与零空间机制，760 任务 | 每个任务同 K 与 raw 估计供 9 个处理方法；N/H/n/r/m、Kstar 与 K0 切片均保留。[实现](E:/ChatGPT/Projects/LQR_experiments/scripts/project2_overnight.py:233) | **公平的机制比较。** Kstar 使用 oracle 起点；经验 c1 阈值的真实误差覆盖未通过 | 单步降噪、零空间分布与 H/N 机制；不称完整学习或阈值证书已验证 |
| F37 中央高预算补点，160 任务 | 看到低预算 PI 失稳后，统一对原 4×40 组合追加 N524288；所有方法同时覆盖；旧 4320 个输出精确重现。[补充方案](E:/ChatGPT/Projects/LQR_experiments/docs/PROJECT2_OVERNIGHT_HIGH_BUDGET_AMENDMENT_20261020.md) | **公平的后续机制补充；不是最初正式网格的独立验证集。** 重算前缀的实际费用另计 | 两臂稳定时依然存在 PI 约 20.14 倍 gap 分离；低预算负点必须与新点一起保留 |
| F38 新固定 K 维秩拟合 | n25/50/100，每格 4×10，统一 N131072/H16，中央只取预定前 10 trials 以匹配重复数。[点表](E:/ChatGPT/Results/LQR_experiments/project2-overnight-20261020/derived/fixed_policy_dimension_rank_points.csv) | **同 cell 误差对照公平；跨 cell 是系统族经验拟合。** 原辅助归一化键缺 policy 的问题已修正 | raw/trunc 的 n 指数 2.893／2.050 可用作 fixed-policy critic 结果；不等同端到端样本指数 |
| F39 旧估计 252 个后处理输出／72 PI 终端／13500 NPG 阶段证书 | 保存估计或策略再评价，无新学习样本；NPG 覆盖 5r×30seed×2方法×45阶段。[证书](E:/ChatGPT/Results/LQR_experiments/project2-overnight-20261020/derived/archived_npg_matrix_region_summary.csv) | **公平的实现与路径检查；不是新增学习重复。** 满秩两臂相同，阶段相关 | P(Kt)≤2P(K0) 的保存路径检查可以采用，13500 不写成独立系统数 |
| F40 大规模 approx-tail，3472 计划配置 | 保存快照 3261 配置，完整 11 profiles 共 2728 配对配置，最高部分档不齐。[范围文件](E:/ChatGPT/Results/LQR_experiments/approx-tail-preview-b16057241cf926bb-20261009-01-review/review/snapshot_scope.json) | **完整 profile 的配对可比；混入不完整档会造成样本选择差异。** 历史 LSTD 白化 | 可用已冻结完整子集的发现；不能给完整 3472 配置的总体末端结论 |
| F41 10 系统多种子 3840 配置计划／本地续跑 | 有部分结果，完整计划未交付；还有明确标成非实验的 report schema fixture。[协议](E:/ChatGPT/Projects/LQR_experiments/docs/RANK_MULTISEED_PROTOCOL.md) | **不能审定为已完成总体对照。** fixture 不计结果 | 不纳入正式主证据，不把计划系统数当作完成复现数 |
| F42 300d NPG 校准／actor 计划 | 现有快照 20 critic、0 完整 actor；各 rank 已有 5 条而非完整计划。[汇总](E:/ChatGPT/Projects/LQR_experiments/docs/LQR_ALL_EXPERIMENTS_20261014.md) | **已完成 critic 内配对可用；不存在完成的 actor 比较。** | 可作估计误差诊断，不作为 300d 端到端正结果 |

## 需要纠正或明确的实质问题

### 1. 同系统后处理收益，与跨 rank 系统比较分别呈现

100d matched-gap 的 r2 CE，恰好同 rank dense 与 r100 dense 都在 14,592 达标，因此两种比值均为 4.38，但来源仍需写清。原 CE500 的 r2 也有同 rank 22.47 倍，足以直接展示截断效果。

等模态 CE500 的 47.16 倍不是同系统比较：A 的不稳定模态数跟着 r 变，K0 按每个系统的最优策略重新构造。该族 r2 dense 只测到 131,328 有效前缀 transitions 仍未达标；不能用 r500 的 1,122,816 替代 r2 dense 的达标预算。random-A 的 5.23 倍虽固定了 A，仍是不同 B／K0 的比较；r2 dense 的正式网格没有覆盖到达标，不能补成有限同 rank 倍率。

全部 CE 对照的同 rank／跨 rank 数字分别保存在 [CE_within_vs_cross_rank.csv](E:/ChatGPT/Projects/LQR_experiments/analysis/fairness-audit-20261022/CE_within_vs_cross_rank.csv)。有中断额外费用的地方保留执行预算区间，不以区间上端伪装精确值。

### 2. 初始化的信息条件确有区别，已有正确控制可用

原 dense stabilizer 的主奇异子空间恰是真实动作空间；matched-gap 的 K0=Kstar+alpha D 虽满秩，仍可能接近真实空间。已保存的实测 r2 重合度分别为 100d 95.96%、原 CE500 98.74%、等模态 CE500 99.75%；随机 r 维空间的相应平均重合度只有 2%、.4%、.4%。

这些 K0 同时给 dense 和截断，故不推翻同系统后处理收益；但不能由它们单独说明从毫无线索的初始化学习子空间。未知几何的论证采用 F03 的 isotropic K0、F17／F35 的相应 PI、以及 K0=0 的小维原始／adaptive 实验即可，不必重跑整个 matched-gap 系列。

来源：[保存系统的子空间计算](E:/ChatGPT/Projects/LQR_experiments/analysis/argument-audit-20261020/initialization_subspace_audit.csv)。random-A 同样按 Kstar 扰动构造 K0；本审核不把上述别的系统族的具体角度数值套到 random-A 上。

### 3. dense 对照公平，但当前回答的是“统一参数下后处理有无用”

新版 PI 的完整 greedy 步长对三臂都为 1；NPG 各 rank／方法采用统一排程；LSTD 两臂解同维度方程、用同一数值容差和求解尝试。没有查到给截断更多训练样本、只对 dense 限制更新数，或在 formal 中只为截断调整步长的处理。

当前 dense 没有独立的大范围步长／H／batch 优化。统一参数是隔离截断作用所需的公平控制，足以支撑论文核心实验；它回答的不是所有可选 dense 实现的最佳性能。known-rank 获得 r 的信息优势已明确；adaptive 的经验 c1 只从观测 split 差异计算，不能把它与 known-rank 不加区分地写成同信息条件。

新一步 NPG 的步长还使用系统构造阶段计算的真实标量 p0_actual 与范数；两臂相同，适合机制比较。完整 v4 PI 的更新不依赖该 NPG 标量。该一步结果不能代替完全数据估计所有常数的算法演示。

### 4. 预算、失稳与中位数的处理必须一致

新 PI 的低档 dense 实际只用 6.293–8.391M transitions 就失稳，分配上限为 12.586M；中档实际 20.974–25.169M，上限 25.169M。三臂是相同上限，失败继续计入分母。最高档全部实际用满 50.335M，最适合说明同实际预算的精度收益。

本轮 actor／一步分布表使用经验逆 CDF，第 ceil(p×n) 个顺序统计量，失败记无穷；因此 8 个系统的“中位数”取第 4 个值。中档 dense 第 4／5 个值平均后是 238.796，而逆 CDF 中位数是 56.902，两者都包含失稳。论文图注应保留分位数定义，不能与旧报告普通中位数混用。最高档换成常规中位数后核心收益仍在，逐系统 known／adaptive 的 gap 比分别在 29.46–36.95／10.80–19.04。

n30/m128 截断的 6.960 是 14 个稳定 seed 的条件中位数。把 6 条失败记无穷后，全部 20 seed 的常规中位数为 **14.162**，达标仍为 0/20。本审核已同时保存两种统计。

中断重算的物理采样不隐藏：等模态 CE500 .1 的主要 47.16 倍不受执行修正影响；random-A .1 的 5.23 倍同样不变。random-A .05 的 full-rank 实际达标预算区间为 1,105,152–1,329,920，r2 为 253,184，因此执行预算比是 **4.37–5.25**，不能只给一个精确倍率。该族 full-rank 自比严格为 1，应采用已修正的 review-v2，原独立区间传播造成的 .831–1.203 不使用。

### 5. 复用与补点已识别，不重复制造“独立验证”数量

v4 PI 用 101–108，旧 damped PI 也用 101–108；冻结系统生成器 hash 相同、系统构造参数相同。新流命名空间 2026102061 与旧 202610142 不同，因此是同系统的新轨迹，不是旧轨迹重放，也不是 8 个新物理系统。pilot 2801／2802 与本轮正式组分离，未查到按 formal 单臂调参。

中央 N524288 是在低预算失稳结果之后追加的。它统一覆盖所有原 4×40 组合，保留旧低预算点，旧前缀逐项重现；没有按有利 seed 补采。它是合理的共同预算补充，论文应与低预算稳定率一起展示；不能只保留这个点来声称低预算也稳定。4 个物理系统的结论也不改写成 160 个独立系统。

### 6. 100d 冗余实验的完整负结果已补入

| m | Dense 终点稳定/20 | 截断终点稳定/20 | Dense 首次失稳阶段范围 | 截断首次失稳阶段范围 |
|---:|---:|---:|---:|---:|
| 8 | 0 | 0 | 6–9 | 7–10 |
| 16 | 0 | 0 | 5–8 | 6–11 |
| 32 | 0 | 0 | 5–6 | 7–12 |
| 64 | 0 | 0 | 4–5 | 8–11 |
| 128 | 0 | 0 | 4 | 7–9 |

两方法在正式配置上匹配：eta=.05、H16、sigma1、48 次分配更新，前 12 步只有 N2048 blocks。全部轨迹在第一段小 batch 尚未结束时失稳，因此后面 N8192／32768／131072 的分配都未执行到。截断常延后失稳，但没有稳定学习成功，更没有达到 g≤.1。

原始 `completion.json` 写 complete 是因为 100 个 paired 任务均返回，不表示学习成功。此前只用 n30 的正结果概括冗余实验不完整；现在两种维数的 200 份 paired 原始文件、9800 组阶段配对均已检查，统计见 [全部 seed 结果](E:/ChatGPT/Projects/LQR_experiments/analysis/fairness-audit-20261022/redundancy_n30_n100_all_seeds.csv)。

若论文只主张 n30 这套受控有效系统中的收益，现有实验足够；若要主张同一排程在 n100 也跑通，需要新的共同早期预算实验。应给两方法一起增加早期 batch，并保持 formal seeds、步长及所有失败记录，不只救截断。本次没有将该失败改写为正结果，也没有启动重复大网格。

### 7. 经验 adaptive 阈值的覆盖检查没有通过

这里检查的误差是 `||[Ghat_+,Zhat]-[G,Z]||op`，阈值是 PSD 后两半样本联合矩阵差的谱范数除以 2，即实际 c1 规则；真实 G/Z 只用于事后核查。中央 n=m50/r4/H16/Kstar 的完整结果如下。

| N | 阈值覆盖真实误差/160 | 真实误差／阈值的常规中位数 |
|---:|---:|---:|
| 8,192 | 0 | 1.1494 |
| 32,768 | 0 | 1.1476 |
| 131,072 | 2 | 1.1433 |
| 524,288 | 0 | 1.1309 |

因此目前 c1 是有性能收益的选秩规则，但不是已通过覆盖检查的高概率误差上界。它通常比被检查的真实误差小约 13%–15%，这与选对有用子空间、降低控制 gap 并不矛盾。源码原本就将 split disagreement 称为经验代理；现在应把实测覆盖结果一起写清。

若论文只论证经验未知秩方法有效，保留当前 c1 与失败边界即可；若要展示理论噪声证书可直接用于选秩，还缺独立 pilot 标定后、固定规则在新数据上的覆盖与性能联合检查。不能在这 160 个正式结果上挑一个刚好覆盖的倍数，再将同批数据当独立验证。现有理论形式的证书与当前 c1 实现不是同一条阈值规则。

此外，13500 个矩阵区域记录来自旧 100d matched-gap NPG，中央零空间／一步数据来自另一组系统与固定 Kstar；它们分别给出路径条件与机制证据，不能拼成“同一条完整轨迹已经逐项验证全部定理条件”。

来源：[全部中央覆盖结果与比值](E:/ChatGPT/Projects/LQR_experiments/analysis/fairness-audit-20261022/empirical_threshold_coverage.csv)。

## 论文组织建议


主结果采用 **同系统** 的 CE100 4.38 倍已测预算节省、NPG100 7.60 倍末端精度收益、原坐标 LSTD PI100 90.44 倍精度收益，以及 v4 PI 的 8 系统成功率／固定预算结果。不同指标放各自面板，避免统一叫“省样本 X 倍”。

未知几何用 isotropic 系列，近似低秩用固定 A／Q／R／K0 的收敛尾部和采样曲线，未知秩同时展示 positive 与 flat／高 rank 反例。等模态及 random-A 的跨 rank 曲线适合补充系统族趋势；n100 冗余的全部失稳应放在冗余实验旁边。当前证据无需整套推倒重跑。

“CE 最省样本”改为“在本次冻结的采样与优化协议中，CE 的已测达标 transition 预算最低”。这些协议在 H、探索、更新次数、调参范围、计算和内存成本上不同，已有实验没有对三个算法进行等计算预算的全面最优调参排名。

## 可复核文件

- [逐轨迹与配对审计脚本](E:/ChatGPT/Projects/LQR_experiments/analysis/fairness-audit-20261022/audit_saved_pairs.py)：只读已有 JSON／CSV 与冻结源码，标准库实现，无仿真、模型求解或新学习样本。
- [机器检查结果](E:/ChatGPT/Projects/LQR_experiments/analysis/fairness-audit-20261022/checks.json)：72 新 PI、300 matched-gap 文件的 7500 组阶段配对、920 个机制任务的共同预算和前缀、两种维数冗余的 9800 组阶段配对。
- [新 PI 的预算、两种中位数与配对比](E:/ChatGPT/Projects/LQR_experiments/analysis/fairness-audit-20261022/v4_actor_budget_and_pairing.csv)。
- [matched-gap NPG／PI 所有 rank 的同系统终点](E:/ChatGPT/Projects/LQR_experiments/analysis/fairness-audit-20261022/matched100_endpoint_comparisons.csv)。
- [CE 同 rank 与跨 rank 分开的完整表](E:/ChatGPT/Projects/LQR_experiments/analysis/fairness-audit-20261022/CE_within_vs_cross_rank.csv)。
- [n30／n100 冗余全部 seed 汇总](E:/ChatGPT/Projects/LQR_experiments/analysis/fairness-audit-20261022/redundancy_n30_n100_all_seeds.csv)。
- [经验 adaptive 阈值的真实误差覆盖](E:/ChatGPT/Projects/LQR_experiments/analysis/fairness-audit-20261022/empirical_threshold_coverage.csv)。
- [输入 SHA256 清单](E:/ChatGPT/Projects/LQR_experiments/analysis/fairness-audit-20261022/input_sha256.json)：记录本次自动检查的原始数据与配置／文档；旧文件保持原样。仅哈希库存不等于对其中每个文件做数学复算。

本次审核记录的是比较设计、信息条件、调参、样本计数、失败处理、版本和复用关系。核心正结果有匹配对照，已识别的失败与跨系统差异一并纳入论文叙述。
