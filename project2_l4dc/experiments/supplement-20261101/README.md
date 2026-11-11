# 2026-11-01 补充实验交付入口

本目录承接同级上层旧四组交付包，所有新结果单独保存。上层 `README.md` / `AUDIT.md`
描述历史恢复任务，在当时确实没有新增学习；本目录新增 X1–X3 正式学习，不混用两者的算法、
种子、分母或预算。论文 TeX、历史结果、冻结 release 均未修改。

当前阶段和作业号见 `RUN_STATE.json`；每次推进的记录见论文工程根目录 `CODEX_REPLY.md`，
审批以 `CLAUDE_TASK.md` 末尾 review log 为准。X0–X3及X4均已报告，X3-NPG正式32个bundle、
1440条路径和93600个输出全部稳定，独立报告作业20359906完成。全部新作业Slurm核时为
**112.920278 /200 SU**，累计申请时限上界159.166667 SU；AMS结算有延迟，不与Slurm相加。
可选X2-NPG n48按已接受的额度决定延期，最终复核见其v2文件。

一行一项清单见 `EXPERIMENT_INVENTORY.md`；去留、三个风险的回答及推荐图表见
`SELECTION_AND_RISKS.md`。NPG整体收益不明确或偏向dense，负结果完整保留；CE是主要正面证据。

| 入口 | 用途与正确口径 |
|---|---|
| `X0/verified_files.json`、`X0/data/` | 恢复128个历史文件：旧01/04以及 independent-A/B、CE500来源；0新计算 |
| `X1/report-ce/`、`X1/report-ce-v2/` | 288条CE轨迹、1728个输出；v2逐输出先归一化 `N D / v*`，同时提供零null控制 |
| `X1/report-actors/` | NPG/PI v4 全部正式终点、逐阶段记录、每臂原始转移计数及配对 bootstrap |
| `X1/report-actors-full-tables-v2/`、`X1/report-actors-figures-v3/` | 每种null、每个m的稳定人数和失败路径；NPG/PI分别出图 |
| `X2/report-ce/`、`X2/report-ce-v2/`、`X2/report-ce-v3/` | 完整预算网格、有限配对比值、失败率、预算到epsilon及右删失；v2/v3为补充 |
| `X2/report-actors/`、`X2/report-actors-figures-v3/` | n12/24正式NPG，相同系统内对比；总gap的CI包含1 |
| `X2/OPTIONAL_N48_BUDGET_DECISION_v1.md` | n48按测量成本延期，Claude03:30接受；不以缩小种子设计替代 |
| `X2/OPTIONAL_N48_BUDGET_DECISION_v2.md` | 最终实际余额87.08SU，仍不足其92.228SU无余量名义外推 |
| `X3/report-ce/`、`X3/report-ce-v2/` | 完整固定k/自适应曲线、事后包络、谱尾及稳定区域显示；完整网格优先 |
| `X3/report-ce-rank-explanation-v4/` | 自适应实际保留秩、阈值、按该秩索引的真实奇异值及最佳固定k |
| `X3/report-ce-failure-detail-v5/` | 自适应真实k分布和失败统计；**取代旧聚合表中adaptive的单一k字段** |
| `analysis-P1-P2-v1/`、`analysis-P1-P2-tables-v2/` | 全部86720个保存NPG迭代的真冗余/动作gap分解、88个物理模型的精确梯度参考；0采样重跑 |
| `X4/formal/`、`X4/report/` | 固定策略扰动诊断，5760次离线评价；包含原本失败和新增失稳；0训练 |
| `packages/*.manifest.json` | 冻结源码、配置、任务资源与归档SHA256；不能编辑归档后复用原收据 |
| `deliveries/*.json`、`*.verified.json` | 远端打包及逐文件传输哈希；归档内保留完整失败/负结果 |
| `budget/ledger.json` | 只累计本研究新作业；`spent_SU`与累计申请时限上界是两种量 |

X3-NPG已提供 `X3/report-actors/`、`report-actors-order-envelope-v2/`、
`report-npg-last-estimator-v1/`，逐阶段失败表在 `report-npg-failure-detail-v3/`。
末阶段分析按 Review04:35，从实际相邻策略重建末次使用的
截断估计，明确区分各臂策略与dense共同策略/共同估计的离线截断。没有对满秩B强行使用
top-2零空间冗余恒等式，也没有重跑采样。

所有新学习的 A 与 B 使用独立随机源，A 开环谱半径1.05；初始策略仅做稳定性修正，
不调用最优解或成本。证书逐系统保存在 `system_certificates.csv`。零null初始化仍位于
动作子空间，这是构造的已披露几何性质；非零null家族和 m=r 基线也明确区分。

CE采用单连续轨迹、512步带高斯探索burn-in、原坐标联合OLS，各方法共享相同完整拟合。
NPG采用Stein相邻pulse-block return差、H32、16个pulse burn blocks及baseline，仅截断Zhat、
保留RK；PI采用PSD clip、joint[G+,Zhat]截断、双侧压缩、完整greedy，单列诊断。
不存在以LSTD critic结果代替正文NPG的情况。超参数由分离pilot上dense规则校准并冻结。

失败使用全32重复分母，gap记为+inf；失稳后吸收计失败，剩余预算在K0下消耗并单列padding，
不当作恢复。配对比值仅在有限配对上定义，同时给有限/全分母和失败人数；不能用组中位数之比
替代逐对比值的中位数。bootstrap按8个独立系统重抽样，保留每系统4个采样seed。

这些实用预算没有逐项认证定理稳定保证的全部充分常数和小误差条件。不能未经数值化便断言
预算严格小于理论常数，也不能把实用排程失稳称为定理反例。NPG报告经验相对比较，同时提供
绝对gap和初始gap归一化gap；不宣称已验证指定epsilon成功率或样本复杂度上界。

X1早期 `report-ce/REPORT.json` 中 `actor_status=REVISE` 是其生成当时的历史状态；后来的
actor批准、完整运行与报告见 `ACCEPTED_ACTOR.json`、`FORMAL_ACTOR_COMPLETE.json`、
`report-actors/REPORT.json`。保留旧收据原文。X3旧 `all_statistics.csv` 和 v3失败表中，
adaptive行的k曾记录首个样本的秩，不能解释为所有重复的统一秩；v5给出正确分布。
该元数据更正不改变任何gap、失败率或原曲线。

在本机复现保存CSV的图，无需连接Grace、求解控制器或安装依赖：

```powershell
& 'E:\anaconda\python.exe' -B 'E:\ChatGPT\Projects\LQR_experiments\project2_l4dc\experiments\supplement-20261101\plot_saved_figures.py'
& 'E:\anaconda\python.exe' -B 'E:\ChatGPT\Projects\LQR_experiments\project2_l4dc\experiments\supplement-20261101\verify_saved_package.py' --require-x3
```

画图输出到新时间戳 `exports/` 子目录，缓存/临时目录固定在本目录 `.runtime/`，既有结果不覆盖。
每份 `PLOT_MANIFEST.json` 记录CSV和PNG/SVG哈希及尚未完成的分支；X3完成前不会画部分结果。
最终CSV重绘在 `exports/csv-reproduction-final-20261101/`，28个PNG/SVG，pending为空，
图中所有数值来自保存CSV，没有重新评价策略或训练。
校验程序只读数据、重新计算保存CSV的中位数/IQR/逐对比值/全分母，并验证旧178文件、X0、
传输包和冻结源码包的哈希。独立目标函数复核已另在Grace计算节点完成；本机校验不伪称重新评价策略。
`--require-x3` 只有最终X3报告到位才通过。正式采样和精确模型评价的历史脚本保留于冻结包内，
不能用画图命令意外重启训练。
