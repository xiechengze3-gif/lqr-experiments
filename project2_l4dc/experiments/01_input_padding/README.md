# 输入补零：原表已恢复

本组8个原报告文件已经从Grace取回并与历史SHA-256逐项匹配，数字只从 `data/report/` 中的CSV读取。

原表来自 Grace 历史快照 `results/final-story-20261024/report/` 中的8个报告文件，
包括 `actor_endpoints.csv`、`ce_all_prefixes.csv` 和 E1 汇总。
精确文件路径、大小、SHA-256及目标位置列于 `../provenance/retrieval_manifest.json`。

本组绘图只提取 `family=E1`；已经核对384条actor终点（NPG192、PI192）和768条CE前缀输出，全部稳定。
每个算法、方法和输入维数单元为24重复；actor各臂实际与分配转移数均为11,805,696。
CE主点为8,192个回归样本，总转移8,324（含132步burn）。
CE可用于主图；旧NPG采用nominal burn，与当前正文pulse-burn NPG协议不同，连同PI仅放附录。
原运行和绘图源码保留在 `../provenance/original/scripts/final_story.py`、`final_story_report_v4.py`。
可移植脚本为 `../scripts/plot_restored_results.py`，由 `../scripts/plot_results.py` 总入口调用；
CE主图、NPG/PI附录图与精确数值底表写入本组 `plots/`。
