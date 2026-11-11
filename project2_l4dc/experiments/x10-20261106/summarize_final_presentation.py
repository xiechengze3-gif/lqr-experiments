"""Format verified saved tables and presentation guidance; no new inference/training."""
import csv,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent
assert (R/'ACTOR_REPORT_DONE_APPEND_RECEIPT_v1.json').exists()
assert json.loads((R/'ACTOR_FULL_RAW_E_COVERAGE_v1.json').read_text())['bundles']==256
def read(name):
    with (R/name).open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
counts=read('failure_counts_by_cell.csv');assert len(counts)==72
assert len({(r['n'],r['algorithm'],float(r['rung'])) for r in counts})==72
totals=[]
for alg in ['NPG','PI']:
    rows=[r for r in counts if r['algorithm']==alg];assert len(rows)==36
    totals.append(dict(algorithm=alg,total_per_arm=sum(int(r['full']) for r in rows),
        dense_failed=sum(int(r['dense_failures']) for r in rows),truncated_failed=sum(int(r['truncated_failures']) for r in rows)))
assert sum(r['dense_failed']+r['truncated_failed'] for r in totals)==len(read('failures.csv'))
note='''# X10b：九档结果的解释与主图范围

本文件只格式化已核验交付中的保存结果，不重算bootstrap或拟合模型。
全部256个新正式任务、1280个新配对路径、2560臂的完整原始状态/估计/策略/检查点
已在E盘核验，旧四档逐字节复用；新五档与旧四档合并为九档。

|算法|每臂合并九档路径数|dense失稳数|截断失稳数|
|---|---:|---:|---:|
'''
for r in totals:note+=f"|{r['algorithm']}|{r['total_per_arm']}|{r['dense_failed']}|{r['truncated_failed']}|\n"
note+='''
NPG最小两档（1/256、1/128）在四个维度的dense臂均32/32失稳。截断NPG只有
n24的1/256档出现13/32失败，其余格均稳定。因此“失败主要在dense”有数据支持，
“截断从不失败”不成立。PI截断在全部九档稳定，PI失败全部来自dense。
这些是输出策略稳定性，不是Slurm作业失败；所有Slurm正式任务和报告均完成。

NPG自1/64起、PI自1/8起，两臂在四个维度均32/32稳定。若主图要求共同稳定
区间，可分别采用这些起点；完整九档图和failure_counts_by_cell.csv必须保留。
PI新增较低预算点多落在dense失稳区，不能把只统计幸存者的有限gap当作其主要
性能，也不能以删除低档点的方式声称全程稳定。已有actor_figures/完整呈现九档、
无穷中位数和每格失败数，适合作为完整结果图。

下表为截断中位gap曲线达到dense满档中位gap所需的描述性样本节省倍数。
使用原论文逐格log-log首次下穿规则；所有八格在九档上均有括区间，无左/右
删失。它与同预算终端配对gap比值不同，也不意味着epsilon成功率保证。

|n=m|NPG曲线匹配节省倍数|PI曲线匹配节省倍数|
|---:|---:|---:|
'''
derived=read('transitions_saved_derived.csv')
for n in [24,36,48,72]:
    a=next(r for r in derived if int(r['n'])==n and r['algorithm']=='NPG')
    b=next(r for r in derived if int(r['n'])==n and r['algorithm']=='PI')
    assert a['left_censored']==a['right_censored']==a['unbracketed']=='False'
    assert b['left_censored']==b['right_censored']==b['unbracketed']=='False'
    note+=f"|{n}|{float(a['factor']):.6g}|{float(b['factor']):.6g}|\n"
note+='''
算法仍为单轨迹Stein NPG（保留RK、只截断Z）及联合左空间压缩的PSD-PI，
eta.2、H16、pulse burn16+baseline1、NPG16次/PI8次，严格按真实转移数配平。
真实rank2没有真实谱尾偏差；低预算仍可能存在估计子空间错误及信号衰减。
这些实用排程没有认证正文定理所需的全部常数、H_t和逐步误差事件，因此不能把
失稳当成该条件性保证的反例，也不能把本实验声称为定理验证。

实际X10b总Slurm消耗123.143055556SU（267历史分配，含原FAILED57秒与两个
零时长取消记录）；AMS已结算相同数值，两者重叠不能相加。申请上界
178.466666667SU/200，正式前保守预测142.270415204/160。所有原始结果、
脚本、配置、图表、失败和删失记录均可从本目录及delivery-actor-report-v1/复核。
论文未修改。X12 n60尚在独立计时pilot阶段，不能用此表替代其未完成的结果。
'''
out=R/'RESULT_INTERPRETATION_v1.md'
with out.open('x',encoding='utf-8') as f:f.write(note)
with (R/'FAILURE_TOTALS_v1.json').open('x') as f:json.dump(dict(status='FORMATTED_VERIFIED_SAVED_COUNTS',totals=totals,
    sources={name:hashlib.sha256((R/name).read_bytes()).hexdigest() for name in ['failure_counts_by_cell.csv','failures.csv','transitions_saved_derived.csv']},
    new_training_transitions=0,new_bootstrap=0,numerical_model_reanalysis=False),f,indent=2)
print(json.dumps(totals))
