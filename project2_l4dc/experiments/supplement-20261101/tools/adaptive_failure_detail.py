"""Correct adaptive-order metadata using every saved output; immutable older tables stay."""
import csv,json
from collections import Counter,defaultdict
from control import ROOT,review,sha,append

def read(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

review();old=ROOT/'X3/report-ce';dest=ROOT/'X3/report-ce-failure-detail-v5';assert not dest.exists();dest.mkdir()
raw=read(old/'all_records.csv');stats=read(old/'all_statistics.csv')
summary={(int(r['n']),r['spectrum'],int(r['N']),r['mode']):r for r in stats if r['metric']=='gap'}
groups=defaultdict(list);by_rank=defaultdict(list)
for r in raw:
    key=(int(r['n']),r['spectrum'],int(r['N']),r['mode']);groups[key].append(r);by_rank[key+(int(r['k']),)].append(r)
full=[];detail=[];varies=0
for key,rows in sorted(groups.items()):
    assert len(rows)==32;hist=Counter(int(r['k']) for r in rows);failed=sum(r['stable']=='False' for r in rows)
    previous=summary[key];assert failed==int(previous['failures']) and 32-failed==int(previous['stable_count'])
    varying=len(hist)>1;varies+=varying
    full.append(dict(n=key[0],spectrum=key[1],N=key[2],method=key[3],category='fixed_k0_diagnostic' if key[3]=='k0' else 'learning_method',
      fixed_retained_k=next(iter(hist)) if not varying else None,retained_order_varies=varying,
      selected_order_histogram=json.dumps(dict(sorted(hist.items())),separators=(',',':')),
      count=32,failed=failed,stable=32-failed,adaptive_selected_k0=hist[0] if key[3].startswith('adaptive') else 0))
for key,rows in sorted(by_rank.items()):
    detail.append(dict(n=key[0],spectrum=key[1],N=key[2],method=key[3],actual_selected_k=key[4],
      category='fixed_k0_diagnostic' if key[3]=='k0' else 'learning_method',
      selected_order_subgroup_count=len(rows),full_method_budget_denominator=32,
      failed_in_selected_order=sum(r['stable']=='False' for r in rows),stable_in_selected_order=sum(r['stable']=='True' for r in rows),
      subgroup_is_data_selected=key[3].startswith('adaptive')))
assert sum(r['count'] for r in full)==sum(r['selected_order_subgroup_count'] for r in detail)==41472
assert sum(r['failed'] for r in full)==sum(r['failed_in_selected_order'] for r in detail)==5747
write(dest/'full_method_budget_failure_counts.csv',full);write(dest/'failure_by_actual_selected_order.csv',detail)
result=dict(status='COMPLETE',source_records_sha256=sha(old/'all_records.csv'),source_statistics_sha256=sha(old/'all_statistics.csv'),
  source_code_sha256=sha(__file__),full_method_budget_cells=len(full),selected_order_subgroups=len(detail),variable_order_cells=varies,
  total_outputs=41472,failed_outputs=5747,diagnostic_fixed_k0_failed=3456,learning_method_failed=2291,
  correction='Older all_statistics/v3 adaptive k field was first observed order; use actual per-output histogram and order subgroups here. Gap/failure/stability totals and figures are unchanged.',
  category_clarification='Adaptive outputs selecting k=0 remain learning-method failures, not fixed-k0 diagnostic outputs.',
  new_learning_runs=0,new_training_transitions=0,provenance='Local standard-library aggregation of existing delivered CSV')
(dest/'REPORT.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
note='''# 自适应选秩元数据更正

历史 `report-ce/all_statistics.csv` 的 adaptive 行的 `k` 字段由单元首条样本填入。
当32次重复的自适应选秩不同时，它不能代表该单元的固定阶数；历史v3失败表继承了该字段。
旧文件按要求保留原字节。gap/relative gap中位数和IQR、失败/稳定人数均按全部32个输出统计，
不依赖该字段；固定k包络排除了adaptive行。因此这些结果、计数和原图不变。

现在以 `full_method_budget_failure_counts.csv` 的完整选秩直方图和
`failure_by_actual_selected_order.csv` 的逐实际k分组为准。后者明确给出数据选择的子组人数和
完整方法/预算分母32，不能把每个自适应k子组都当成32次重复。

类别名改为 learning_method，避免暗示自适应选择始终>=1。固定k0是单独诊断；自适应阈值
选到k0的输出仍计入相应学习方法的失败，未被移到诊断行。总数仍为5747：固定k0诊断3456，
其余学习方法2291。先前v4自适应解释表从逐输出读取k，已经正确，继续有效。
这次只整理已有CSV，没有新拟合、采样、策略评价或实验运行。
'''
(dest/'README.md').write_bytes(note.encode())
body='Scope: X3 CE adaptive-order metadata correction, saved data only. The old aggregate `k` field on adaptive rows retained the first observed order; it must not be read as a fixed order for all32 outputs. Original bytes are preserved.\n\n'
body+=f'New `X3/report-ce-failure-detail-v5/` provides{len(full)} full method/budget cells and{len(detail)} actual-selected-order subgroups;{varies} cells have varying selected orders. Every full cell still has32 outputs; each adaptive-order subgroup shows its selected count beside the full32 denominator. All gap/IQR, failure totals and figures remain unchanged.\n\n'
body+='The category is now `learning_method`, not a label suggesting every selected k>=1. Fixed-k0 diagnostic failures3456 remain separate; adaptive methods selecting k0 remain their own learning failures. Total5747, learning2291, unchanged. The v4 adaptive-explanation table already used per-output k and remains correct. README/REPORT give the exact supersession and hashes. Zero model fitting/evaluation/learning runs.\n'
(ROOT/'X3/adaptive_failure_metadata_correction.md').write_bytes(body.encode());append('X3','REPORT',body)
print(json.dumps(result))
