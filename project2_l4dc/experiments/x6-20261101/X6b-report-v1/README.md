# X6b REPORT 完整交付

科学结论、设置、定理解释及呈现建议见[SCIENCE_REPORT.md](SCIENCE_REPORT.md)。
数字取自本目录原始CSV，所有10份文件均与计算节点冻结汇总及封存报告逐字节匹配。

|入口|内容|
|---|---|
|summary.csv|64格：32注册实验格×两种配对比值定义，含完整分母、gap/IQR、padding和CI|
|attainment.csv|32格：epsilon观测阶梯、成功数、CI、右删失和bootstrap删失质量|
|diagnostic_summary.csv|逐更新、逐臂、逐版本的误差、投影及显式有效分母|
|endpoints.csv / stages.csv / diagnostics.csv|2048终端、26624阶段及逐路径诊断记录|
|paired_endpoints.csv / system_summaries.csv|配对及系统层次数据，保留全部种子|
|epsilon_ratios.csv / stage_summary.csv|条件epsilon比值及完整阶段统计|
|tables/|全部档的绝对/相对gap及IQR、两种比值CI、epsilon、诊断和代价分解|
|figures-v4/|最终三对PNG/SVG和输入/输出哈希；原v2/v3检查稿保留|
|verification.json / SOURCE_HASHES.json|冻结分析输出、科学源码、配置及32个系统文件哈希|
|FIGURE_QA_v4.json / table-manifest.json|实际视觉检查与仅格式化表格的审计|
|FINAL_ACCOUNTING_v1.json|全部作业结束后的独立账目；不依赖封包中的早期快照|

正式归档ef73e587...已验证51592个文件，报告归档1b0242a7...已验证
534个文件。完整原始结果在../X6b-protocol-v2/deliveries/formal-v1/；
原始封存包及清单在../X6b-protocol-v2/transfers/。DELIVERY_MANIFEST.json记录完整SHA和本地收据。
这些文件数含控制记录、日志及账目快照，不等同于统计样本数。

数值检查：所有36864个原始矩阵/检查点文件哈希通过，连续性和更新公式最大误差均0；
终端gap分解最大相对误差6.40861399e-16，
直接代价恒等式最大相对误差9.49989633e-13。
384个正式任务及5个REPORT任务均COMPLETED，没有自动重试、取消或排程改动。
REPORT零新增转移；正式网格的训练转移总数483160776704。

X6最终累计申请上界343.366666667/400SU；
完成后Slurm计费242.363888889SU，
AMS当时已结算242.290277778SU，
快照时间2026-11-02T14:43:51.517237+00:00。两者重叠，不相加；AMS仍有结算时差。
旧X0–X4是独立已完成研究，不计入这里的X6数值。

复现展示：使用../X6b-protocol-v2/plot_saved_actor_v4.py --report 本目录 --out 一个新E盘目录。
表格由同目录make_report_tables.py从已保存CSV生成；数值分析源码analyze_actor.py保持冻结SHA
ec27555202189295f5d46db3c4d51684e1344db58ffea44eb3acd9965bb55469。
模拟及数值分析仅在Grace Slurm计算节点运行，本机只做哈希/CSV格式化/绘图。
冻结v14正式包、v15报告包、配置和每次整数batch仍在X6b-protocol-v2内，旧结果和论文tex未改。

阶段已交付后继续等待Claude review；X6c仍DEFERRED，不因剩余额度自动新增实验。
