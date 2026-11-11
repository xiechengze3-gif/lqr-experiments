这些表的“行数”不等于独立重复数。每个正式统计单元为8个独立系统×4个采样seed，共32条路径；
同一条路径可以保存多个前缀、阶段或诊断输出。X4每单元320是8×4×10个固定扰动评价，
独立系统仍为8。P2人口参考每单元只有8个物理模型，不能按重复采样seed复制成32个独立模型。

| 字段/文件 | 定义 |
|---|---|
| `system`, `trial` | 植物随机源和采样随机源；pilot与formal集合分离 |
| `stable` | 该输出按固定Schur稳定容差通过；不等于认证定理中的P区域或高概率路径条件 |
| `gap` | `J(K)-J*`；失败原始行可为null/空，汇总按+inf |
| `relative_gap` | 同系统同初始策略的gap除以`J(K0)-J*`，每输出归一化后再汇总 |
| `count`, `full_denominator` | 完整计划重复32；不是有限配对数 |
| `stable_count`, `failures` | 全分母稳定/失败人数；允许中位数有限但上四分位数为inf |
| `median`, `q25`, `q75` | 失败包含的分位数；+inf不插值成有限数，线性有限分位数与脚本一致 |
| `finite_pairs` | dense和比较方法都稳定且分母gap>0的配对数；排除失败的比值不代替全分母误差 |
| `paired_ratio_median` | 先逐system/trial计算dense/method，再取中位数；不是两个组中位数的比 |
| `bootstrap95_*` | 2,000次按8个系统重抽样，保留其4个trial的区间；各报告记录固定seed |
| CE `N` | burn之后用于OLS的共同回归前缀转移数；`transitions=N+512` |
| CE `N_over_d` | `N/(n+m)`；epsilon表是整数化sqrt(2)预算网格，无达标项右删失 |
| actor `planned_transitions` | 所有更新的pulse burn、baseline及学习blocks的原始转移总和 |
| actor `actual_transitions` | 实际模拟转移，独立pulse计数复核；正常完成每臂精确等于计划 |
| `padding_transitions` | 吸收失败之后在K0下消耗而丢弃的转移；含在实际总数内，不是额外加项或恢复样本 |
| `whole_path_stable` | 全记录路径通过稳定检查；先失败后预算padding不会重新变成成功 |
| `hard_failure` | 代码/数值异常导致部分运行；保存已产生数据，不自动重放；与政策失稳分开 |
| X1 `null_scale` | 0为动作子空间内稳定化初值；.25为隐藏子空间的null项，匹配仅对m>r成立 |
| X1 `redundant_cost` / P1 `redundant_D` | 真输入零空间的闭环稳态代价；R=I时`tr(K_null Sigma K_null^T)` |
| P1 `action_gap` | 真投影策略`Pi K`的gap；逐输出满足`gap=D+action_gap`，不能相加两个分量中位数 |
| P1 `D_over_gap` | 每输出D/g，然后取中位数/IQR；不是中位数之比 |
| P1 `null_error_fro2` / `action_error_fro2` | `||U_null^T(K-K*)||F²` / `||V_r^T(K-K*)||F²`；U_null指输入ker(B) |
| P2 `population_relative_gap` | 同K0、同冻结eta/T、同正式物理模型下精确梯度参考；零样本，另计模型数 |
| X3固定k包络 | 对固定k组的失败包含中位数取最小，是事后诊断；不是每条路径用真值选优或在线adaptive |
| X3 `tau_k_squared`, `beta_k` | 该表按真B的谱定义；NPG实际截断Zhat，不能解释为每个当前Z_K的谱尾 |
| X3 adaptive 的 `k` | 每个原始输出有真实选择k；旧aggregate单一k为首样本值，统一改用v5真实分布 |
| X3 last `effective_estimate` | 从实际K_(T-1)、K_T重建的已截断矩阵；不是截断臂未保存的raw Zhat |
| X3 last `target` | 各实际K_(T-1)处的`Z_K=-B^T P_K(A-BK)`，独立真模型评价 |
| X3 last `own_arm_actual_update` | 各k臂的真实末次更新；不同k有不同状态与策略 |
| X3 last `common_dense_policy_and_raw_estimate` | 同一dense末次raw估计离线取五种秩；没有额外学习或反事实endpoint |
| X3 last `valid_estimators` | 可恢复实际末次更新的数量；缺失误差不伪造为一次观测，endpoint失败仍以+inf计 |
| X4 `source_failed_count` | 原策略已经失败的继承输出；每个失败源策略×10方向×3尺度计30个失败评价 |
| X4 `new_instability_count` | 原稳定策略在扰动系统上新增失稳，和继承失败分开 |
| X4相对gap | 扰动K0稳定时才定义该扰动初值归一化；分母缺失不是学得策略失稳，另给源初值归一化 |
| ledger `spent_SU` | 本研究新作业已运行核时（Slurm有效billing×ElapsedRaw），含运行中累计，快照有UTC |
| ledger `requested_total_bound_SU` | 累计申请时限的保守上界，含保留的零秒失败/拒绝预留；不是已花SU |

任何“达到epsilon”的说法都必须给定义、全部成功人数、要求人数、预算与删失。NPG仅比较
固定预算实际结果；三个4倍间隔的X3预算不能用来报告满足sqrt(2)网格要求的精度达标预算。
