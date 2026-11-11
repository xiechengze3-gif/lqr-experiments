"""Post hoc uncertainty supplement for the already fixed X11 point statistic."""
import ast,csv,hashlib,json,math,os,sys
from pathlib import Path
R=Path(__file__).resolve().parent;C=R.parents[1];D=R/'uncertainty-report-v1'
sys.path.insert(0,str(R/'src-v1'))
import frozen_engine as e
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','NUMBA_NUM_THREADS']:assert os.environ[key]=='1'
for key in ['TEMP','TMP','TMPDIR','XDG_CACHE_HOME','NUMBA_CACHE_DIR','MPLCONFIGDIR']:
    p=Path(os.environ[key]);assert p.drive.upper()=='E:' and p.is_dir()
assert not os.environ.get('SLURM_JOB_ID')
assert json.loads((R/'REPORT_DONE_v1.json').read_text())['status']=='REPORT_COMPLETE'
source=R/'report-v2';proof=json.loads((source/'REPORT_GENERATED.json').read_text())
names=['new_records.csv','reused_records.csv','paired_gap_ratios_by_N.csv']
for name in names:assert sha(source/name)==proof['files'][name]
assert sha(R/'src-v1/frozen_engine.py')=='9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989'
legacy=(R.parent/'x10-20261106/ce-src-v2/analyze_ce.py').read_text()
q_source=next(ast.get_source_segment(legacy,n) for n in ast.parse(legacy).body if isinstance(n,ast.FunctionDef) and n.name=='q')
exec(compile(q_source,'unchanged_original_q','exec'))
D.mkdir()
protocol=dict(status='POST_HOC_UNCERTAINTY_SUPPLEMENT_PREPARED_BEFORE_THIS_ANALYSIS',
    motivation='Global F8 asks system-level bootstrap CI; accepted X11 point report supplied IQR but omitted bootstrap CI.',
    timing_disclosure='Analysis seed and resampling plan are registered after formal data and original report; never describe as original preregistration.',
    unchanged_point_statistic='median_system(median_seed(dense_gap/truncated_gap))',
    repetitions=5000,cluster_unit='system',systems=list(range(301,309)),seeds=list(range(1601,1605)),
    resample='8 whole system clusters with replacement; retain all4 paired seeds within each selected cluster',
    rng='frozen_engine.rng(620,11,n,m); one common index array per cell for every N and both ratio kinds',
    interval='pointwise percentile95%; original q(.025)/q(.975); no simultaneous-probability interpretation',
    source_csvs={name:sha(source/name) for name in names},source_sha256=sha(Path(__file__)),
    new_training_transitions=0,Grace_SU=0,original_files_untouched=True,primary_costs_figures_and_point_estimates_unchanged=True)
with (D/'PROTOCOL.json').open('x') as f:json.dump(protocol,f,indent=2)
def read(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
records=read(source/'new_records.csv')+read(source/'reused_records.csv')
for r in records:
    for key in ['n','m','system','seed','N']:r[key]=int(r[key])
    r['stable']=r['stable']=='True';r['gap']=float(r['gap'])
assert len(records)==4160 and all(r['stable'] and math.isfinite(r['gap']) and r['gap']>0 for r in records)
old=read(source/'paired_gap_ratios_by_N.csv');assert len(old)==130
result=[];draw_proofs=[]
for n,m in sorted({(r['n'],r['m']) for r in records}):
    subset=[r for r in records if r['n']==n and r['m']==m]
    draws=e.rng(620,11,n,m).integers(0,8,size=(5000,8))
    draw_proofs.append(dict(n=n,m=m,shape=list(draws.shape),draw_sha256=hashlib.sha256(draws.tobytes()).hexdigest()))
    for N in sorted({r['N'] for r in subset}):
        cells={}
        for r in subset:
            if r['N']==N:cells.setdefault((r['system'],r['seed']),{})[r['arm']]=r['gap']
        assert len(cells)==32 and all(set(v)=={'dense','truncated'} for v in cells.values())
        medians=[q([cells[system,seed]['dense']/cells[system,seed]['truncated'] for seed in range(1601,1605)],.5) for system in range(301,309)]
        point=q(medians,.5)
        bootstrap=[q([medians[int(i)] for i in draw],.5) for draw in draws]
        assert len(bootstrap)==5000 and all(math.isfinite(x) for x in bootstrap)
        lower,upper=q(bootstrap,.025),q(bootstrap,.975)
        for kind in ['both_stable','failure_inclusive']:
            row=next(r for r in old if int(r['n'])==n and int(r['m'])==m and int(r['N'])==N and r['ratio_kind']==kind)
            assert float(row['median'])==point and int(row['eligible_pairs'])==32 and int(row['systems'])==8
            result.append(dict(row,ci_low=lower,ci_high=upper,bootstrap_repetitions=5000,bootstrap_valid=5000,bootstrap_invalid=0,
                bootstrap_cluster_unit='system',bootstrap_systems=8,common_draws_across_N_and_ratio_kinds=True,
                pointwise_interval=True,post_hoc_uncertainty_plan=True))
fields=list(result[0])
with (D/'paired_gap_ratios_by_N_with_CI.csv').open('x',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(result)
assert len(result)==130
with (D/'DRAW_IDENTITIES.json').open('x') as f:json.dump(draw_proofs,f,indent=2)
text='''# X11 配对比值的不确定性补充

原 X11 已被接受的逐档配对比值文件给出中位数和IQR，遗漏了全局F8要求的系统级
bootstrap区间。本补充只给既定点统计增加区间，属于正式数据和原报告完成后的
后补分析。随机种子、重采样规则和重复数在本次分析前写入PROTOCOL.json；不能
将它描述成原先的正式预注册。

点统计仍是：先算同系统同种子的dense/truncated gap比，取每个系统4种子的
中位数，再取8个系统中位数的中位数。8个系统整群有放回重采样5000次，每群
保留4个配对种子。每个(n,m)使用frozen_engine.rng(620,11,n,m)的一套共同
重采样索引，跨所有N和两种ratio_kind复用。区间为逐格95%百分位区间，不能
视为全部曲线的同时置信带或总体成功概率保证。

全部130行的原始字段原样保留，点中位数逐行精确复现；补充字段为CI、重复数、
有效/无效质量和方法标签。所有4160条新/复用的arm-prefix记录均稳定且gap有限，
因此两种比值定义在此补充中一致，全部重复有效。原始拟合/轨迹、原CSV、
样本成本、图表和既有结论均未修改；没有新数据采集、模型求解或训练，GraceSU0。

文件：paired_gap_ratios_by_N_with_CI.csv、PROTOCOL.json、DRAW_IDENTITIES.json、
VERIFIED.json。全部源CSV的原有SHA已按report-v2/REPORT_GENERATED.json核对。
'''
with (D/'REPORT.md').open('x',encoding='utf-8') as f:f.write(text)
final=dict(status='SUPPLEMENT_COMPLETE_POINTS_EXACTLY_PRESERVED',rows=130,bootstrap_repetitions=5000,all_draws_valid=True,
    post_hoc_uncertainty_plan=True,new_training_transitions=0,Grace_SU=0,original_files_untouched=True,
    files={p.name:sha(p) for p in D.iterdir() if p.is_file()})
with (D/'VERIFIED.json').open('x') as f:json.dump(final,f,indent=2)
with (C/'CODEX_REPLY.md').open('a',encoding='utf-8') as f:
    f.write('\n## X11 REPORT uncertainty supplement\n\nCaught an omission: the accepted X11 paired-ratio CSV had IQR but no system-bootstrap CI as globalF8 asks. Added a separate saved-record-only uncertainty-report-v1/ supplement, no old file edit. Its resampling plan/seed were registered AFTER formal data/original report and BEFORE this supplementary calculation; explicitly labeled post-hoc, not original preregistration. Same fixed median_system(median_seed pairedratio), whole8system clusters/4pairedseeds,5000replicates, fixedrng(620,11,n,m), commondrawsacrossN/kinds, pointwise95% percentileCI. All130old point rows exactly reproduced; all draw mass retained. SourceCSVhashes checked, source/seed/draw/file proofs included. 0newtrajectories/modelsolves/training/GraceSU. Original REPORT/figures/costs/raw remain intact. Please review supplemental uncertainty alongside alreadyacceptedoriginalreport.\nSTATUS: REPORT SUPPLEMENT DONE X11\n')
print(json.dumps({k:v for k,v in final.items() if k!='files'}),flush=True)
