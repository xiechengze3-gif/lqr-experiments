# CE100匹配gap与高秩CE：原表已恢复

本组24个原报告文件已经从Grace取回并与历史SHA-256逐项匹配；预算与误差只从随包CSV读取。

原表分为 `data/matched_ce/`、`data/matched_npg/`、`data/precision_ce/`、`data/adaptive_ce/` 四个子目录，共24文件。
精确历史快照路径、大小、SHA-256及目标位置列于 `../provenance/retrieval_manifest.json`。
正式matched结果目录是 `report-confirm`，不是 `report-formal`。

建议表1仅采用同系统dense/truncated CE预算与精细高秩CE结果。
旧matched NPG使用nominal burn，仅作附录实践版；经验adaptive CE也仅作附录。
不得把rank100 dense与rank2 truncated的跨系统预算比称为同系统截断收益。

已从原表复核：匹配gap的r2 CE相对0.1达标预算为dense14,592、truncated3,328；同系统预算比约4.38。
高秩CE的r16/32/64/100精细预算为dense141,824/160,256/184,832/156,160、
truncated64,000/113,152/170,496/156,160。以上高秩预算**已含512步burn**，达标要求是各单元2/2系统达到绝对gap0.1，不是30重复的90%成功标准。

高秩precision CE的2,880个输出全部稳定；经验adaptive原表4,320个输出中的8个失稳均在最低预算1,024，全部保留。
旧matched NPG的13,500个保存阶段、300条终点全部稳定；r2同预算终端gap为
dense0.13215756970074466、truncated0.017391795159277024，组中位数比7.598845805762034。
其截断方法确实在27,794,544和94,905,228转移分别达到相对0.1和0.05；原达标表保留为附录事实，不宣称理论充分条件得到认证。

原绘图/报告程序保留在 `../provenance/original/scripts/` 的
`ce_matched_initial_gap_report.py`、`ce_precision_zoom.py`、`ce_adaptive_zoom.py`、
`matched_gap_npg_pi_report.py`。可移植脚本为 `../scripts/plot_restored_results.py`，由
`../scripts/plot_results.py` 总入口调用；图和精确底表写入本组 `plots/`。
