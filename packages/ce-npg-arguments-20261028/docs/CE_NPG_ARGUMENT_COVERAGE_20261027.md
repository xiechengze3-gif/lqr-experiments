# CE / NPG 按论证点的证据覆盖（2026-10-27）

本清单依据本地现有协议、源码、报告及完成收据；没有重新查询 Grace、恢复历史全量结果、
重跑学习或重新核验所有远端哈希。用户此次要求是后续实验与正文组织的基准。
新方案见[修订协议](CE_NPG_ARGUMENT_PROTOCOL_20261027.md)。

|要求|现有 CE 证据|现有 NPG 证据|后续处理|
|---|---|---|---|
|严格低秩 gap–transitions|10/27，n=12/24/48/96、r2，两类 A；同 OLS 的 dense/model-SVD|10/27，n12/r2，两类 A；各臂连续轨迹|图1两条路线并列；CE 可复用，NPG 补同族维度与秩变化|
|维度/秩变化及同精度预算|10/27 主要变化 n；历史 100d 有 rank sweep|10/08 有 n25/50/75/100 和 r1/2/4/8/16，10/17 有 100d rank sweep|历史可作独立证据；初始化和排程不同，不拼进同族统计。新增统一低维网格|
|同一满秩实例内扫描 k|10/27 两段谱和平滑谱，n16，多前缀、多 k|10/24 平滑谱 .6^j、A=.7I，有多 k、多预算；10/27 只有固定 k2/k4|复用历史 NPG 平滑谱作为补充；补统一系统下两谱 NPG 秩扫描|
|固定 k、增加数据与谱尾关系|10/27 固定 k 随 N；旧 approximate-tail 有尾扫描|10/27 固定 k 随 M；旧 approximate-tail 有尾扫描/population 参考|增加同族可调 delta；记录 B、Z_K 的不同尾部，保留 NPG 振荡/偏差负结果|
|平坦谱负对照|历史自适应四谱含 flat；10/27 本轮没有|历史四谱经验自适应对照不能替代给定 k 的同族学习|新增同族 flat，至少比较强截断、中间秩、dense|
|D(K) 与 g(Pi_R K) 的直接分解|10/27 原始 CSV 已有 gap、redundant_cost、projected_cost|10/27 exact 全轨迹已有同列；首阶段共同 blocks 有单步代价|先重组已有数据作图2；中位数须分别配对统计，不能靠总体中位数相减|
|CE 同一完整估计的机制对照|10/27 共享 OLS，截断 Bhat 再求 gain|不适用|现有实现已符合可用 main.pdf 式(10)/Theorem 7(a)；补组合图与分解，不新增 gain 截断算法|
|NPG 固定当前 K 的共享 blocks 单步|不适用|10/27 K0 首阶段已保存；不同路径后续没有同 K 保证|首阶段诊断已满足基本要求；新增固定 stage 的条件对照，完整运行另外呈现|
|未知秩适应|10/27 adaptive CE，冻结 c1 的经验 split 代理及所选秩|当前无需对称增加未知秩 NPG|嵌入图3。代理不冒称理论置信半径；历史 adaptive NPG 负结果不删除|
|一般未知动力学/连续轨迹/失败|10/27 独立 dense A=.5O，估计 A/B；全失败分母|10/27 独立 dense A、连续 state；burn/baseline 全计数|在新网格继续保持；0 失败是该已完成轮的结果，不是新网格保证|
|PI 与问题类下界|历史多种 PI 实现需要对应审计|不适用|匹配实现的 PI 对照放附录；不设计有限算法实验去“证明”普遍下界|

## 对已经完成一轮的准确表述

10 月 27 日完成的是 576 条正式采集轨迹，而不是本次修订要求的全部覆盖。
该轮 NPG 已有 exact / 两段满秩 / 平滑满秩的学习结果和首阶段机制证据，
不能说 NPG 从未测试过 approximate rank；其缺口是**同族维度/秩扫描及满秩多 k 扫描**。
10 月 24 日的 NPG 多 k 结果也确实存在，不能因本轮图按算法分组就忽略。

本次保留 10 月 27 日全部冻结记录。README 新增修订入口，后续正文改为
“CE/NPG 学习与维度、CE/NPG 冗余成本、CE/NPG 满秩谱并嵌入 adaptive CE”三张组合图。
新增方案是可审阅的候选配置，尚无新 runner、正式作业或新增实验结果。

## 文稿版本与算法名称

本地 [project2_paper_body.tex](../source/project2_paper_body.tex) 为 10 月早期技术正文，
其开头明确省略 Introduction 和 experiments，不能当作用户当前正文的定理编号依据。
[10/27 输入收据](../receipts/manuscript-three-groups-20261027-input.json) 记录先前实际使用的是
桌面 main.pdf，指定名 main(2).pdf 当时未找到。此次重新计算桌面 main.pdf 的 SHA256，
与该收据的 89365e363c43ab14520b8294edd271feb4c3f8774ab7744fe9dfea8940d600ea 一致；
并提取全文、渲染检查第 4、6 页。可用版本的同数据 CE separation 编号为 Theorem 7(a)，
定义正是 LQR(Ahat,Bhat) 对 LQR(Ahat,T_r(Bhat))，已与现有实现核对一致。
用户所述 8(a) 应保留版本编号差异，不臆断可用 PDF 含有该编号。
该 PDF 的理论 adaptive CE 使用 LS 误差半径阈值；已有 split 代理只作为经验版本呈现。

## 证据入口

- [10/27 完成结果](MANUSCRIPT_THREE_GROUPS_FINDINGS_20261027.md)、[冻结协议](MANUSCRIPT_THREE_GROUPS_PROTOCOL_20261027.md)、[完成收据](../receipts/manuscript-three-groups-20261027-complete.json)。
- [10/27 全部输出](../local_runs/manuscript-three-groups-20261027/report/all_records.csv)、[共同 blocks 单步](../local_runs/manuscript-three-groups-20261027/report/same_blocks_diagnostic.csv)。
- [10/24 NPG 满秩多秩结果与失败](FINAL_STORY_FINDINGS_20261024.md)、[其冻结协议](FINAL_STORY_PROTOCOL_20261024.md)。
- [10/08 NPG 维度/秩扫描及斜率解释边界](NPG_RANK_FINDINGS_20261008.md)。
- [100d CE/NPG rank sweep](RANK_SWEEP100_FINDINGS_20261017.md)、[LSTD PI 附录候选](RANK_SWEEP100_PI_FINDINGS_20261018.md)。
- [历史自适应四谱](ADAPTIVE_RANK_FINDINGS_20261011.md)、[近似谱协议](APPROX_TAIL_SUITE_PROTOCOL.md)、[存储与按需恢复](GRACE_RESULTS_STORAGE.md)。
