# L4DC 实验交付与筛选

本目录按用户确认的位置建立：`E:\ChatGPT\Projects\LQR_experiments\project2_l4dc\experiments`。
本次只提取已有结果、审核算法版本并绘图；新增学习、数据采集和控制方程求解均为 0。

**四组原始数值均已到位。** 第 1、4 组的 32 个历史报告文件已从 Grace 取回，逐文件与原始 SHA-256 一致。
所有图表只读取随包 CSV，不从说明文档抄数补成数据。机器可读状态见 `package_status.json`；绘图和最终校验分别见 `plot_status.json`、`validation.json`。

| 目录 | 内容 | 当前状态 | 建议用途 |
|---|---|---|---|
| `01_input_padding/` | 固定有效系统、增加补零输入的 CE/NPG；PI 仅作附录 | 8 个原报告文件已恢复；E1 的384条actor和768条CE输出均稳定 | CE 可用于主图；旧 NPG 的 burn 协议有差异，只作附录实践版比较 |
| `02_same_data_decomposition/` | n24/r2，两类 A 的同 OLS CE 分解、同 K0/blocks 的首步 NPG 对照 | 已提取 1,008 条 CE 和 96 条 NPG 输出 | 优先主机制图 |
| `03_fullrank_rank_scan/` | 两段谱、平滑谱的保留秩扫描，平坦谱负对照 | 已提取 54,264 条相关输出 | 优先主图；平坦谱 NPG 只有 k2/k8/dense 三种方法 |
| `04_ce100_matched_gap_and_high_rank/` | 匹配初始 gap 的 CE/NPG、高秩 CE 精细预算与经验 adaptive CE | 24 个原报告文件已恢复；精细CE原表和NPG阶段表已复核 | 表格以 CE 为主；旧 NPG 只作附录实践版比较 |

相关输出不是独立重复。第 2、3 组每个统计单元均为 24 个重复（3 个系统 seed × 8 个采样 seed）；
不能把全部保存前缀/阶段的行数当成重复数。

按正文算法一致性的严格口径，建议图(a)为CE输入补零与最新pulse-burn NPG同数据机制，
图(b)为最新固定k CE/NPG满秩扫描及平坦谱对照，表1为CE100匹配gap和高秩CE。
旧nominal-burn NPG、PI和经验half-split adaptive CE均只作附录。
即使核心算法形式相符，固定实用schedule仍未数值认证Theorem 3的全部充分条件。

`AUDIT.md` 回答三个风险问题、列出版本差异和不适合主文的实验；`algorithm_versions.csv` 是逐路线版本表。
查阅的论文快照实验节仍是 TODO，图(a)/图(b)/表1仅为建议映射，没有修改论文正文、推送或上传。

## 数值与来源

- `data/*.csv` 保留原始数值精度和字段，没有四舍五入后回填。
- `provenance/extractions.json` 记录每份提取的筛选条件、来源和 SHA-256。
- `provenance/original/` 保留原始配置、运行/画图源码及依赖、报告说明、完成/校验收据。
- `provenance/paper_snapshot/` 仅是用于比对算法的论文快照，不代表本包修改后的论文。
- `appendix/data/exact_rank_npg_endpoints.csv` 保留所有 576 条严格低秩 NPG 的终点（包括失败）。
- `appendix/data/tail_strength_all_outputs.csv` 保留额外大/小尾部强度对照。
- 失败率使用全部计划重复；主图选取完整共同预算单元，不能删掉失败种子再画幸存者。
- 所有误差与比值必须注明同系统/跨系统、固定预算/固定精度，不能互换。

## 复现

使用已有 `E:\anaconda\python.exe`，不需要安装依赖。包内绘图只读 CSV，不重新学习或评价控制策略。

```powershell
& 'E:\anaconda\python.exe' '.\scripts\plot_results.py'
& 'E:\anaconda\python.exe' '.\scripts\verify_package.py'
```

总入口 `plot_results.py` 覆盖四组，并调用 `plot_restored_results.py` 处理恢复的第 1、4 组。
图和数值底表写入各组的 `plots/`，根目录 `plot_status.json` 记录各组状态。
缓存和临时目录固定为包内 `.runtime/`，不使用 C 盘默认缓存。
原始历史画图程序保留在 `provenance/original/scripts/`；这些程序依赖各自原始实验目录。
移植后的统一入口只读取本包数据，不需要恢复完整学习轨迹或原始远端目录结构。

完整性检查输出 `validation.json` 与 `SHA256SUMS`。最终交付需同时满足 `available_data_checks_passed=true`、
`all_four_groups_complete=true` 和四组绘图状态均为 `complete`。

## 历史结果恢复记录

本地原结果已于 10 月迁至 Grace。`provenance/retrieval_manifest.json` 列出所需 **32 文件、6,164,961 字节**，
含远端路径、目标相对路径、原始大小和 SHA-256；无需下载全部学习轨迹或大型归档。

用户完成交互登录后，正常 Windows 用户环境于 `2026-11-01T05:29:34.1630362Z` 验证现有共享连接成功，
目标主机为 `login5`。随后复用该连接取回全部32文件；未关闭或重启主连接。
以下命令保留供日后按需校验恢复，已经通过校验的文件会跳过下载：

```powershell
& '.\scripts\restore_archived_results.ps1'
& 'E:\anaconda\python.exe' '.\scripts\assemble_package.py'
```

恢复脚本仅下载缺失的结果并逐文件验证哈希；共享连接不能验证时立即停止，不启动新登录、不改主连接。
恢复后已按原表核对字段与预算单位；高秩CE表中的 `budget` 已包含512步burn，不能再加512。
经验adaptive CE最低预算的8个失稳输出保留，不能删除后宣称所有输出稳定。
