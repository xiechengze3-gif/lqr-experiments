"""Finalize verified delivery metadata; stdlib-only,zero new numerical analysis."""
import datetime
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'X6b-report-v1'
CHANNEL=ROOT.parents[2]
REVIEW='d5747708372e246b7bfd394c9c33ed915f4c7a20e6370aa1718032ba6b605e2e'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def js(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def main():
    assert sha(CHANNEL/'CLAUDE_TASK.md')==REVIEW
    assert not (OUT/'DELIVERY_MANIFEST.json').exists()
    config_path=ROOT/'prepared-formal-v1/formal-config.json'
    config=js(config_path)
    assert sha(config_path)=='6c0c63610119ef895cda3af4174589bcbd7cf06ab0e7c26d99df3d5bdec7398d'
    for name,digest in config['scientific_sources'].items():assert sha(ROOT/name)==digest
    for model in config['model_registry'].values():assert sha(ROOT/'prepared-formal-v1'/model['path'])==model['sha256']
    archives={}
    for scope,count,digest in [
        ('formal',51592,'ef73e5871033bae2a1065ae047ad7e49bde5b9f6eed72738765c61df94c7a5e2'),
        ('report',534,'1b0242a7949f9801ca314b53aacbf482f664ad634841b18a935d552bbdbe09b6')]:
        manifest_path=ROOT/'transfers'/('x6b-'+scope+'-v1.tar.json')
        manifest=js(manifest_path);receipt_path=ROOT/'deliveries'/(scope+'-v1.verified.json')
        receipt=js(receipt_path)
        assert manifest['status']=='SEALED' and manifest['scope']==scope
        assert manifest['archive_sha256']==receipt['archive_sha256']==digest
        assert receipt['status']=='VERIFIED_EXTRACTED' and receipt['files']==len(manifest['files'])==count
        archive_path=ROOT/'transfers'/manifest['archive']
        archives[scope]=dict(files=count,archive_sha256=digest,archive=str(archive_path),
            bytes=archive_path.stat().st_size,manifest=str(manifest_path),
            manifest_sha256=sha(manifest_path),local_verification=str(receipt_path),
            local_verification_sha256=sha(receipt_path))
    raw=ROOT/'deliveries/formal-v1/X6b/formal-v1'
    assert sha(raw/'FORMAL_COMPLETE_v1.json')==sha(ROOT/'FORMAL_COMPLETE_v1.json')=='24a8f47691822bef40349012e6fc6d5e0f9721640cca3efec58f34b97025d7be'
    coverage=js(ROOT/'FORMAL_COMPLETE_v1.json')
    proof=js(OUT/'verification.json')
    assert proof['status']=='COMPLETE' and proof['endpoint_rows']==2048 and proof['paired_cells']==64 and proof['attainment_cells']==32
    assert proof['source_sha256']==config['scientific_sources']['analyze_actor.py']
    assert proof['config_sha256']==sha(config_path)
    extracted=ROOT/'deliveries/report-v1/X6b/report-v1/summary'
    for name,digest in proof['files'].items():
        assert sha(OUT/name)==sha(extracted/name)==digest
    assert sha(OUT/'verification.json')==sha(extracted/'verification.json')
    diagnostics=js(ROOT/'DIAGNOSTICS_COMPLETE_v15.json')
    assert all(r['state'][0]=='COMPLETED' and r['verification']['status']=='COMPLETE'
               and r['verification']['max_K_continuity_error']==0
               and r['verification']['max_update_relative_error']==0 for r in diagnostics['rows'])
    complete=js(ROOT/'REPORT_JOB_COMPLETE_v15.json')
    assert complete['sacct'].strip()=='20367367_0|COMPLETED|265'
    figure_manifest=js(OUT/'figures-v4/manifest.json')
    assert figure_manifest['source_sha256']==sha(ROOT/'plot_saved_actor_v4.py')
    for name,digest in figure_manifest['figures'].items():assert sha(OUT/'figures-v4'/name)==digest
    qa=js(OUT/'FIGURE_QA_v4.json')
    assert qa['status']=='VISUALLY_REVIEWED_PASS' and qa['source_sha256']==figure_manifest['source_sha256']
    for name,digest in qa['checked_png_sha256'].items():assert sha(OUT/'figures-v4'/name)==digest
    table_manifest=js(OUT/'table-manifest.json')
    assert table_manifest['source_sha256']==sha(ROOT/'make_report_tables.py')
    for name,digest in table_manifest['tables'].items():assert sha(OUT/'tables'/name)==digest
    accounting=js(OUT/'FINAL_ACCOUNTING_v1.json')
    assert accounting['cumulative_requested_SU']<=accounting['cap_requested_SU']==400
    sources=dict(config_sha256=sha(config_path),scientific_sources=config['scientific_sources'],
        model_registry=config['model_registry'],presentation_source_sha256=sha(ROOT/'plot_saved_actor_v4.py'),
        table_formatter_sha256=sha(ROOT/'make_report_tables.py'),
        report_release_archive_sha256='5c0296532d1a7d86245d98aa447225a84004876da139ca381b28db07261c4a7b')
    (OUT/'SOURCE_HASHES.json').write_text(json.dumps(sources,indent=2)+'\n',encoding='utf-8')
    readme=f"""# X6b REPORT 完整交付

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

正式归档ef73e587...已验证{archives['formal']['files']}个文件，报告归档1b0242a7...已验证
{archives['report']['files']}个文件。完整原始结果在../X6b-protocol-v2/deliveries/formal-v1/；
原始封存包及清单在../X6b-protocol-v2/transfers/。DELIVERY_MANIFEST.json记录完整SHA和本地收据。
这些文件数含控制记录、日志及账目快照，不等同于统计样本数。

数值检查：所有36864个原始矩阵/检查点文件哈希通过，连续性和更新公式最大误差均0；
终端gap分解最大相对误差{proof['max_gap_decomposition_error']:.9g}，
直接代价恒等式最大相对误差{proof['max_cost_identity_error']:.9g}。
384个正式任务及5个REPORT任务均COMPLETED，没有自动重试、取消或排程改动。
REPORT零新增转移；正式网格的训练转移总数483160776704。

X6最终累计申请上界{accounting['cumulative_requested_SU']:.9f}/400SU；
完成后Slurm计费{accounting['slurm_elapsed_billing_SU']:.9f}SU，
AMS当时已结算{accounting['ams_settled_walltime_slots_SU']:.9f}SU，
快照时间{accounting['checked_utc']}。两者重叠，不相加；AMS仍有结算时差。
旧X0–X4是独立已完成研究，不计入这里的X6数值。

复现展示：使用../X6b-protocol-v2/plot_saved_actor_v4.py --report 本目录 --out 一个新E盘目录。
表格由同目录make_report_tables.py从已保存CSV生成；数值分析源码analyze_actor.py保持冻结SHA
ec27555202189295f5d46db3c4d51684e1344db58ffea44eb3acd9965bb55469。
模拟及数值分析仅在Grace Slurm计算节点运行，本机只做哈希/CSV格式化/绘图。
冻结v14正式包、v15报告包、配置和每次整数batch仍在X6b-protocol-v2内，旧结果和论文tex未改。

阶段已交付后继续等待Claude review；X6c仍DEFERRED，不因剩余额度自动新增实验。
"""
    (OUT/'README.md').write_text(readme,encoding='utf-8')
    inventory={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}
    result=dict(status='COMPLETE_LOCAL_DELIVERY_VERIFIED',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        review_sha256=REVIEW,archives=archives,coverage=coverage['counts'],
        failure_counts=coverage['failure_counts'],summary=proof,
        diagnostics_verified_artifacts=sum(r['verification']['verified_artifacts'] for r in diagnostics['rows']),
        accounting=accounting,final_figure_directory='figures-v4',files=inventory,
        metadata_note='Sealed archives capture logs/accounting during REPORT; FINAL_ACCOUNTING_v1 is a separate post-completion snapshot.',
        zero_new_transitions_report=True,scientific_sources_unchanged=True,paper_tex_edited=False)
    assert sha(CHANNEL/'CLAUDE_TASK.md')==REVIEW
    (OUT/'DELIVERY_MANIFEST.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],files=len(inventory),archives=archives,
        figure_qa=qa['status'],manifest_sha256=sha(OUT/'DELIVERY_MANIFEST.json'))))

if __name__=='__main__':main()
