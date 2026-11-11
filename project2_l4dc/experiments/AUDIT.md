# 实验选择、算法版本与风险审核

审核日期：2026-11-01。本文只审核和整理既有实验，不提交新学习任务，不修改论文正文。

## 交付范围与状态

本目录是当前可写工作区内的实验交付包：`E:/ChatGPT/Projects/LQR_experiments/project2_l4dc/experiments/`。它不是已经确认的论文主工作副本。所见最新论文快照为 `E:/ChatGPT/Temp/project2_l4dc_round13final_d9716c69/project/`；其中 `main.aux` 将 `thm:e2e` 编为 Theorem 3，但 `sections/06-experiments.tex` 仍为 TODO。因此下面的图 (a)、图 (b) 和表 1 是**建议映射**，不能说已经核实了既有图号。

| 组目录 | 内容 | 当前数据状态 | 建议用途 |
| --- | --- | --- | --- |
| `01_input_padding` | final-story E1：固定有效系统，改变补零输入维数 | 8个原报告文件已恢复并通过历史SHA-256 | 图 (a) 保留 CE 输入补零；旧 NPG 和 PI 仅附录 |
| `02_same_data_decomposition` | 最新 CE/NPG 的同数据单步与真实冗余损失分解 | 本地结果 CSV 可用 | 图 (a) 的机制面板；优先选全重复稳定的共同 K0 单步对照 |
| `03_fullrank_rank_scan` | 两段谱、平滑谱的固定 k 扫描，含平坦谱负对照 | 本地结果 CSV 可用 | 图 (b)：CE/NPG 有效秩权衡；平坦谱必须保留 |
| `04_ce100_matched_gap_and_high_rank` | 100 维 matched-gap CE、高秩 CE；历史 NPG 附录 | 24个原报告文件已恢复并通过历史SHA-256 | 表 1 采用 CE；NPG 作为明确标注版本的附录比较 |

01/04 的32个报告文件现已从Grace取回，历史SHA-256逐项一致；下面的相关分母、误差与预算已从原CSV复核。不得用说明文档反造CSV，也不得把旧收据或结论文本充作原始观测。01来源为本包 `01_input_padding/data/report/`；04来源为 `04_ce100_matched_gap_and_high_rank/data/` 下四个子目录。02/03最新本地报告来源为 `local_runs/ce-npg-arguments-20261028/report/`，归一化来源为 `local_runs/ce-npg-initial-gap-20261028/report/`；后两条路径相对于 `E:/ChatGPT/Projects/LQR_experiments/`。

## 风险一：失稳主要在哪一边，与 Theorem 3 的关系

**最新严格低秩 NPG 中，dense 失稳更多；但不是所有实验都如此。** 下表不混合不同实验、不同预算或不同方法的分母。

| 数据范围 | dense | truncated | 证据与可写结论 |
| --- | --- | --- | --- |
| 最新 exact-rank NPG，全部维度、秩、两种 A | 163/288 失稳，56.60% | 65/288 失稳，22.57% | 本地 `endpoint_all_denominators.csv` 的 `algorithm=NPG,spectrum=exact`，按 `mode` 汇总 `failed_count/count`；文档总数见 `docs/CE_NPG_ARGUMENT_FINDINGS_20261028.md`。截断减少失稳，但仍有65条失稳。 |
| 最新 n24/r8，标量 A | 24/24 失稳 | 24/24 失稳 | 同一终端表。该条件下两者均失败，不构成截断成功案例。 |
| 最新 n24/r8，耦合 A | 24/24 失稳 | 18/24 失稳 | 同一终端表；截断仍只6/24稳定。 |
| 最新满秩 NPG，含两段谱、平滑谱、尾强度和平坦谱 | 全部固定 k 合计0/1032失稳 | 同左；不是1032条dense/truncated配对 | 本地同一终端表的 `algorithm=NPG,spectrum!=exact`；所有模式均稳定，可用于同预算秩扫描。 |
| 输入补零 E1 | NPG 0/96失稳；PI 0/96 | NPG 0/96失稳；PI 0/96 | 本包 `01_input_padding/data/report/actor_endpoints.csv` 筛选 `family=E1` 已复算；各算法×方法×m均24/24稳定。NPG共192条，含PI共384条。 |
| 100维matched-gap NPG | 0/150条轨迹失稳 | 0/150条轨迹失稳 | 本包 `04_ce100_matched_gap_and_high_rank/data/matched_npg/npg-all-checkpoints.csv`：13,500个阶段与300个终点均稳定且whole_path_stable。 |
| 历史 n100 动作冗余，沿用早期排程 | 100/100失稳 | 100/100失稳 | `docs/PROJECT2_EXPERIMENT_FAIRNESS_AUDIT_20261022.md` F24记载，200条全部失败。它不是输入补零E1，也不是100维matched-gap；不放主图。 |

Theorem 3 的稳定保证以充分的误差精度、horizon、batch、burn-in和系统条件为前提。实用冻结排程没有把定理未知常数数值化，也没有逐阶段验证其充分条件。严谨表述是：

> 实验采用有限预算的预先固定实用排程，未按理论常数认证 Theorem 3 的充分条件；因此这里的经验失稳不构成对满足该定理条件的稳定保证的直接检验。截断在部分条件下降低了经验失稳率。

**不要未经计算直接写“预算低于理论常数”。** 未知常数没有数值化时，不能断言某一预算与理论门槛的大小关系。也不能把 Schur 稳定等同于 `P_K <= 2 P_K0`。最新文档还记载498条NPG轨迹至少一个稳定阶段违反该矩阵区域；这是未认证理论路径条件的另一个原因，原始逐阶段字段见 `all_records.csv` 的 `P_relative_max`、`NPG_containment`。

主图只展示预先按实验设置确定的稳定预算区间时，必须同时给出全分母失败率和完整预算结果的附录入口，不能按种子删失败、用幸存者中位数代替全分母表现。失稳后的计划阶段继续计失败；失败包含的gap中位数为正无穷时不画成有限值。

## 风险二：每组实际算法及与正文的距离

正文对应公式是 `K_CE=LQR(Ahat,T_k(Bhat))` 和 `K_next=K-eta*(R*K+T_k(Zhat))`。NPG的Zhat是相邻block-return差分的Stein residual估计，不是LSTD critic；CE同时估计A和B，不是已知A。所有转移预算应计入burn和baseline。

完整逐版本表见 [algorithm_versions.csv](algorithm_versions.csv)。重要区别如下。

### 01：输入补零

- CE：同一连续行为轨迹、132步nominal burn，同一完整OLS拟合，Ahat保持不变，只截断Bhat后求DARE；原表 `ce_all_prefixes.csv` 已确认主点8192个回归转移、总8324，E1全部768个前缀输出稳定。来源实现为 `scripts/final_story.py` 的 `ce_run`。可保留主图；不要把下面 NPG 的 pulse-block burn 要求套用于 CE 连续回归采样。
- NPG：`scripts/final_story.py:actor` 调 `scripts/project2_overnight.py:collect_prefixes`；相邻return Stein、只截断Zhat、保留RK，eta=1/9、H=12，132步**无探索的nominal burn**，随后一个pulse baseline；64次更新，每16次batch为Nfinal/8、Nfinal/4、Nfinal/2、Nfinal，Nfinal=32768。原终点表已确认每臂实际与分配均为11,805,696转移。完整路径各自连续，分叉后只共享外生创新，不共享观测。
- 同组PI是v4：PSD修正G、joint `[G+,Z]` SVD、G双侧压缩、完整greedy更新。它不是正文CE/NPG，放附录。

**协议差异不能省略：** 最新论文 `sections/app/C-statistics.tex` 的固定Stein阶段要求burn-in的每个block也有pulse；01旧NPG的nominal burn不满足这个逐项协议描述。按用户“主图和表必须使用正文算法”的要求，**01旧NPG仅作为附录实践版，不能通过在图注加“实践版”而进入主图**。此处pulse-block要求针对NPG，不作为排除01 CE的理由。01 PI也只在附录保留。

### 02：同数据冗余分解

- CE：`scripts/ce_npg_argument_run.py:ce_task`；K0=0，144步带探索burn；连续OLS，同一(Ahat,Bhat)供dense和B-SVD合成。真实子空间只用于离线评价，不进入学习。
- NPG：同文件 `collect/actor_task`；每阶段12个**pulse burn blocks**、1个baseline、H=12、eta=1/9；48次更新，每12次blocks=2048/8192/32768/131072，总分配25,075,008转移。核心估计器与更新式符合正文形式；固定参数未经过理论充分条件认证。
- 推荐首阶段共同K0、共同blocks、共同Zhat的单步dense/truncated对照。`same_blocks_diagnostic.csv` 中两个来源臂相同的首阶段只算一个数据对，不重复计数。stage24/48只有来源路径存活时才有记录，不能用它们替代全重复首阶段对照。
- 真实冗余损失D仅在严格低秩系统定义；CE截断使用估计空间，因此真实D一般不为0。不能把“D减小”写成“精确消除真实零空间代价”。

### 03：满秩k扫描与平坦谱

- 固定k CE/NPG沿用02相同估计器和连续轨迹协议。n=m=16，两段谱和平滑谱分别扫描k=0/1/2/3/4/6/8/12/16；dense就是k16。k0是额外诊断，正文算法的r从1开始，不宣称k0验证了该形式的定理。
- 平坦谱NPG只有k2、k8、dense三方法，不是九秩完整扫描。其结论是强截断有害，必须保留。
- Adaptive CE使用固定c=1的half-split disagreement：`threshold=||Bhat_half1-Bhat_half2||op/2`。这是经验代理；**不是正文经理论常数校准的LS置信半径**。本次严格按正文版本筛选主图，经验自适应CE放附录，不能说直接认证了adaptive corollary。
- 本组没有新增adaptive NPG。历史冻结adaptive NPG过度截断是负结果，不能换图例当成本组算法。

### 04：100维matched-gap与高秩CE

- matched-gap CE：`scripts/ce_matched_initial_gap.py` 复用 `scripts/rank_sweep100.py:ce_task`；256步nominal burn、sigma=2，稳定K0下单连续OLS，同Ahat、B-SVD后DARE，30个正式采样seed。K0私下由Kstar+alpha D构造，学习器不接收Kstar，但这仍是特殊初始化，不能称无几何信息的独立随机稳定器。
- 高秩CE：`scripts/ce_precision_zoom.py` 调 `dense_scaling.ce`；512步nominal burn、sigma=1，两系统、每系统一个采样seed、180个共同前缀。只作有限系统的离散预算对照，不拟合普遍rank定律。高秩adaptive仍是经验half-split阈值。
- matched-gap NPG附录：`scripts/matched_gap_npg_pi.py`→`scripts/rank_sweep100.py:npg_task`→`scripts/actuation_redundancy.py:collect`；相邻return Stein、保留RK、只截断Zhat，eta=.05、H=4、256步nominal burn，每阶段一个baseline，44次更新：blocks=16384/65536/262144/1048576各8次、4194304共12次；每臂最大245,902,512转移。因旧nominal-burn与当前pulse-burn理论协议不同，**仅作附录实践版，不进入主图或表1**。
- matched-gap LSTD-PI拟合全部20,100个原坐标二次critic系数，后处理joint `[G,C]`；它不是Stein-NPG，也不是01的v4 PI，不进入正文CE/NPG表。
- 高秩CE的A/B/K0联合设计；matched-gap的K0围绕Kstar构造。两者系统族和初始化均要在图注或表注披露。来源：`docs/PROJECT2_K0_A_B_CONSTRUCTION_AUDIT_20261022.md`。

04原表已确认以下数值和不利条件：

- matched CE在相对0.1（初始gap=1，亦为绝对0.1）的首达预算，r2/8/32/64/100分别为dense14,592/16,640/24,832/20,736/14,592，truncated3,328/8,448/16,640/20,736/14,592，均含256步burn。首达时dense各为30/30成功；truncated各为29/30、30/30、27/30、30/30、30/30。不能把末端全部30/30成功误写成首次达标全部30/30。
- 高秩precision CE的2,880个输出无失稳；adaptive CE的4,320个输出有8个失稳，均来自4个rank×2个系统的最低预算1,024。原不利点保留。
- 高秩表 `budget` 已含512步burn，不能再次加512。r16/32/64/100达到绝对gap0.1的dense预算为141,824/160,256/184,832/156,160；known-rank和经验adaptive均为64,000/113,152/170,496/156,160。标准是2/2系统达标，不是30重复的90%标准。

## 风险三：NPG是否只做相对比较

**本次选入主图的NPG只支持dense与truncated的相对表现比较，不声称已经验证指定epsilon精度或样本复杂度上界。** 仍同时提供absolute gap和初始gap归一化指标：

`relative_gap=(J(K)-Jstar)/(J(K0)-Jstar)`。

“只做相对比较”指算法间的经验对比，不意味着只能展示归一化纵轴。不能把稳定性改善等同于达到高精度。

最新n24、真实秩r=1/2/4/8、两种A、dense/truncated的相对10%目标，都未达到至少22/24成功。来源为本地 `local_runs/ce-npg-initial-gap-20261028/report/attainment_side_by_side.csv`：过滤 `algorithm=NPG,spectrum=exact,n=24,epsilon=0.1`，检查 `relative_right_censored`、`relative_success_count_at_maximum`。全部失败和未达标均保留。

这不等于所有历史NPG都没有达标。04原 `npg-all-checkpoints.csv` 与 `sample_complexity.csv` 已确认，初始gap=1时r2截断NPG在27,794,544和94,905,228转移分别达到相对0.1和0.05，首达时均30/30成功；同rank dense直到最大245,902,512预算仍未达这两个目标。它们只作为该特定系统、该实践版排程的附录事实，不能用来声称最新n24网格达到相对10%，也不能移用其90%标准至两系统高秩CE。

共同最大预算下r2的dense/truncated终端gap中位数为0.13215756970074466/0.017391795159277024，组中位数比为7.598845805762034。这是同rank固定预算精度比较；rank100 dense与rank2 truncated的约8.24353倍达标预算比属于跨系统比较，不能称为同系统截断省样本倍率。

## 建议图表与实验去留

| 位置 | 建议选入 | 必须伴随的说明 |
| --- | --- | --- |
| 图 (a) | 01的CE输入补零收益；02最新pulse-burn NPG及CE的全重复共同K0单步分解 | 01旧NPG排除在主图外；01原表已恢复验证；02共享数据只限该单步；每子图报告全分母失败率 |
| 图 (b) | 03两段谱、平滑谱的固定k CE/NPG；平坦谱负对照 | 最新pulse-burn NPG；经验adaptive CE放附录；预算包含burn/baseline；k0和下包络仅诊断；固定schedule未逐项认证Theorem 3 |
| 表 1 | 04的matched-gap CE同系统dense/truncated；高秩CE精细预算表 | 从已验证原CSV读取；高秩CE只有2系统，匹配gap与高秩实验不是同一系统族 |
| 附录 | 01旧nominal-burn NPG和v4 PI、04旧nominal-burn matched NPG、经验adaptive CE、耦合A复现、完整失败/删失表 | 旧NPG只能作附录实践版；标清版本、预算和初始化；不作跨算法排名；04原坐标LSTD-PI仅保留版本参考，本次未选其完整checkpoint原表 |
| 不作主证据 | n100旧冗余排程200条全失稳、最新高维/高秩exact NPG、冻结adaptive NPG、部分完成大网格 | 保留负结果和入口，不把失败区间换成幸存者图，不把未完成计划写成已完成 |

旧高秩CE粗网格的“4倍”不能沿用：原表 `precision_ce/sample_to_accuracy.csv` 已复核精细预算，r16约2.22倍、r32约1.42倍、r64约1.08倍。matched-gap的跨rank预算比也不能冒充同系统截断收益；同系统倍率必须从相同rank的dense/truncated表格计算。

## 数字来源与复核规则

1. 主图/表的数字只从随包既有CSV读取；源文件、筛选条件、分母和预算定义在绘图脚本或清单中保留。
2. 全分母失败率与稳定子集误差分别报告；轨迹、前缀输出、反事实输出、系统种子不能混作独立重复数。
3. 每个固定精度预算须保留实际成功人数、要求人数、最大已测预算、删失标记；未达到不得外推。
4. 01/04恢复的32个原表与历史哈希逐项一致，没有用文档重建数值。相关旧文档仅作解释与版本对照：`docs/FINAL_STORY_FINDINGS_20261024.md`、`docs/CE_MATCHED_INITIAL_GAP_FINDINGS_20261018.md`、`docs/MATCHED_GAP_NPG_PI_FINDINGS_20261019.md`、`docs/CE_PRECISION_ZOOM_FINDINGS.md`、`docs/CE_ADAPTIVE_ZOOM_FINDINGS.md`。
5. 本文不声称核实了理论常数、定理成功概率或所有路径条件；参数与理论协议的差异见 `algorithm_versions.csv`。
