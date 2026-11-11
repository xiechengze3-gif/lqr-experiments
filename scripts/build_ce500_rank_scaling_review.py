"""Assemble a compact bilingual saved-results review, with embedded figures."""
import argparse
import base64
import csv
import hashlib
import html
import json
from pathlib import Path
import shutil
import zipfile


def main():
    p=argparse.ArgumentParser();p.add_argument('--rank4-root',type=Path,required=True)
    p.add_argument('--analysis',type=Path,required=True);p.add_argument('--cost',type=Path,required=True);a=p.parse_args()
    source=a.rank4_root/'report-confirm';out=a.analysis;out.mkdir(parents=True,exist_ok=True)
    with (source/'sample_complexity.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    with (source/'fixed_budget_rank_scaling.csv').open(encoding='utf-8-sig',newline='') as f:fixed=list(csv.DictReader(f))
    fit=json.loads((source/'scaling_analysis.json').read_text(encoding='utf-8'))
    extra=json.loads((out/'additional_scaling_analysis.json').read_text(encoding='utf-8'))
    cost=json.loads(a.cost.read_text(encoding='utf-8'))
    cost_status='全部入账' if cost['all_measured_jobs_settled'] else f"尚有 {len(cost['missing_measured_job_ids'])} 个任务待入账"
    def req(r,m,t):return next(q for q in rows if int(q['rank'])==r and q['method']==m and float(q['relative_target'])==t)
    def val(q,k='N_hat_90'):return f'{float(q[k]):,.0f}' if q[k] else 'not reached'
    table=[]
    for rank in [2,4,8,32,64,500]:
        m='dense' if rank==500 else 'truncated';x=req(rank,m,.1);y=req(rank,m,.05)
        table.append('<tr><td>'+str(rank)+('</td><td>dense reference' if rank==500 else '</td><td>truncated')+'</td><td>'+val(x)+'</td><td>'+val(y)+'</td></tr>')
    fit_text=[]
    for q in fit['results']:
        if q['metric']=='fixed_budget_affine_fit':
            fit_text.append(f"N={q['transitions']:,}: median gap ≈ {q['intercept']:.6g} + {q['slope']:.6g} r; R²={q['R_squared']:.6f}; max relative residual={100*q['max_relative_residual']:.2f}%.")
    images=[]
    for name in ['sample_complexity_rank_2_4_8_32','fixed_budget_gap_vs_rank','success_probability_rank_2_4_8_32']:
        png=source/(name+'.png');data=base64.b64encode(png.read_bytes()).decode('ascii')
        images.append('<img alt="'+html.escape(name)+'" src="data:image/png;base64,'+data+'">')
        for ext in ['png','svg']:shutil.copyfile(source/(name+'.'+ext),out/(name+'.'+ext))
    convergence=out/'rank4_gap_convergence.png'
    if convergence.exists():
        images.append('<img alt="rank4 gap convergence" src="data:image/png;base64,'+base64.b64encode(convergence.read_bytes()).decode('ascii')+'">')
    for name in ['sample_complexity.csv','success_by_budget.csv','fixed_budget_rank_scaling.csv','rank_scaling_comparison.csv','scaling_analysis.json','audit.json','summary.json']:
        shutil.copyfile(source/name,out/name)
    shutil.copyfile(a.rank4_root/'frozen/config.json',out/'rank4_frozen_config.json')
    shutil.copyfile(a.rank4_root/'resource_plan.json',out/'resource_plan.json')
    shutil.copyfile(a.cost,out/'cost-summary.json')
    for name in ['analyze_ce500_rank_scaling_saved.py','plot_ce500_rank4_convergence_saved.py',
                 'verify_ce500_rank4_download.py','build_ce500_rank_scaling_review.py']:
        shutil.copyfile(Path(__file__).resolve().parent/name,out/name)
    report='''<!doctype html><meta charset="utf-8"><title>CE500 rank scaling</title>
<style>body{font:16px/1.6 system-ui,sans-serif;max-width:1120px;margin:35px auto;padding:0 20px;color:#20252b}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:9px;text-align:right}td:first-child,th:first-child{text-align:left}img{width:100%;height:auto;margin:20px 0}small{color:#556}</style>
<h1>CE500：固定初始 optimality gap 的 rank 对照</h1>
<p>初始 gap = 1；relative targets 0.1/0.05 等于 absolute targets 0.1/0.05。下表 N̂90 是至少 27/30 个策略在真实系统稳定且达标的第一个测试预算；包含 256 transitions burn-in。各 rank 共享 A、U、V、初始化方向与配对外生噪声，初始控制器分别校准到 gap=1。</p>
<table><thead><tr><th>Rank</th><th>CE version</th><th>N̂90 target 0.1</th><th>N̂90 target 0.05</th></tr></thead><tbody>'''+''.join(table)+'''</tbody></table>
<p>这是预先冻结的离散预算网格上的估计。预算区间与 bootstrap 区间分别记录在 CSV 中。30/30 的 Wilson 95% 成功率区间为 [88.65%,100%]，并不证明总体成功率至少为 90%。</p>
<p>低 rank 区间存在明显的样本需求差异；严格 N∝r 与“带截距的近似线性趋势”是不同判断。固定预算的拟合结果如下，仅用于描述这个共同随机系统：</p><ul>'''+''.join('<li>'+html.escape(s)+'</li>' for s in fit_text)+'''</ul>
<p>Gap 对 rank 的描述性拟合不能直接证明样本复杂度定律。改变 rank 同时改变控制能力、初始控制器和探索分布，不能把跨 rank 趋势直接归因于估计器。完整数据保留 rank 64 与 500；低 rank 拟合只使用 2/4/8/32。</p>
'''+''.join(images)+'''<p>CE 从实际 trajectory 联合 OLS 恢复 [Ahat,Bhat]，无 ridge、无样本白化。Dense/truncated 共用 Ahat 和原始 Bhat，仅截断 Bhat 后使用相同 Riccati 求解器。新增 rank 4 全部 900 个正式策略已独立复核 gap；30 个最终 OLS 已从 checkpoint 重算；原有 4050 个策略审计和 full-rank dense/truncated 一致性验证按 manifest 复用。</p>
<p>运行问题：提交前修正校验清单 CRLF；pilot 读取软件库模块有约 5 分钟启动延迟，未来正式 walltime 从 25 增至 30 分钟。学习算法、随机源和预算不变。环境中保留了非致命 BLAS 版本探测警告。旧实验的 3 次资源超时及已验证不影响 N̂90 的费用区间仍保留在原结果中。</p>
<p>本轮费用状态：'''+cost_status+'；已结算 AMS SU（逐作业舍入合计）：'+f"{cost['actual_AMS_settled_rounded_SU']:.2f}"+'；Slurm allocated core hours：'+f"{cost['allocated_core_hours']:.3f}"+'''。两者分别报告，未结算任务不记作零成本。</p>
<small>本页由保存的结果直接生成；完整原始记录、策略、模型估计、断点、配置和文件校验清单位于独立的 rank-4 结果目录。既有五个 rank 的结果保持不变。</small>'''
    (out/'results.html').write_text(report,encoding='utf-8')
    manifest={str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.iterdir()) if f.is_file() and f.name!='review_sha256.json'}
    (out/'review_sha256.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.iterdir()):
            if f.is_file():z.write(f,arcname=f.name)
    print(json.dumps(dict(review=str(out/'results.html'),zip=str(archive),zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=len(manifest)+1,fit_text=fit_text),indent=2))


if __name__=='__main__':main()
