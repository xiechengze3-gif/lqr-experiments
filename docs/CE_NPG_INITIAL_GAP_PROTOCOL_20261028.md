# 初始gap归一化补充：仅复用已有输出（2026-10-28）

本次由用户明确要求：CE/NPG学习曲线及达标预算同时给absolute和相对初始gap，
保留所有失稳、未达标记录，不重新运行学习实验。

输入仅为已完成研究 `ce-npg-arguments-20261028/report` 中的
`all_records.csv`、`system_certificates.json`、`fixed_accuracy.csv`，
冻结哈希见[配置](../configs/ce_npg_initial_gap_postprocess_20261028.json)。
不访问raw轨迹、不生成数据、不更新策略、不解新的Riccati或Lyapunov方程。

逐实例定义 g0=J(K0)-Jstar，relative=g(K)/g0；先对每个输出归一化，再取全分母中位数。
g0必须严格为正；若为0则明确报告未定义，不对分母作数值截断。
同一个物理系统的所有方法使用同一g0。以保存的relative_gap列逐值核对。

固定精度在两种定义下都取epsilon=0.1、0.03、0.01。
达标预算沿用首个已测预算上至少22/24成功的规则。relative epsilon=0.1表示
剩余不超过初始可改善损失的10%，不是额外成本占Jstar的10%。
每个instance的relative epsilon对应absolute容差epsilon*g0。

失败按正无穷计入两种指标；NPG一旦失稳，后续全部计划预算继续失败。
未达标保留最大已测预算并标右删失，不插值、不外推，不把稳定子集均值或中位数当全分母。
个体首次达标、NPG连续4点确认和后续失稳分别记录；首次达标不等于终端或持续达标。
原absolute表144行必须逐项复现，避免更换统计口径。

图表包括：CE和NPG各自的三维度absolute/relative并列学习图；固定精度预算并列图；
耦合A复现、固定n的rank扫描、两段/平滑满秩谱和平坦谱并列曲线。
完整CSV覆盖全部设置和全部方法，不仅是主图选取的单元。

只在Grace真实Slurm计算节点做数值报告。申请1 CPU、2GiB、最多6分钟，
本次后处理请求上限0.1核时；新增学习运行与训练transitions均为0。
缓存/临时目录显式设于项目scratch。完整旧报告保持不变，输出另存新研究目录。
本地源码、配置、图表和收据均存E盘。复用现有共享连接，不修改任何主连接或现有作业。
