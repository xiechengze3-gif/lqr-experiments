"""Correct only a coupled self-comparison interval; immutable original archive."""
import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def html_row(q):
    return (f"<tr><td>{q['rank']}</td><td>{q['relative_target']}</td>"
            f"<td>{q['truncated_N90_lower']:,}–{q['truncated_N90_upper']:,}</td>"
            f"<td>{q['sample_saving_lower']:.3f}–{q['sample_saving_upper']:.3f}</td></tr>")


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    args=p.parse_args();cfg=read(args.manifest);out=Path(cfg['output'])
    archive=read(out/'archive_receipt.json');assert archive['status']=='complete'
    source=out/'report-confirm';dest=out/'review-v2';assert not dest.exists()
    shutil.copytree(source,dest)
    original=read(source/'execution_cost_audit.json');corrected=copy.deepcopy(original)
    assert original['status']=='PASS'
    fields=['sample_saving_lower','sample_saving_upper','bootstrap95_saving_lower','bootstrap95_saving_upper']
    changed=[]
    for q in corrected['low_rank_vs_full_rank']:
        if q['rank']==cfg['n']:
            changed.append(dict(rank=q['rank'],relative_target=q['relative_target'],
                previous={k:q[k] for k in fields},corrected={k:1.0 for k in fields}))
            q.update({k:1.0 for k in fields})
    for a,b in zip(original['low_rank_vs_full_rank'],corrected['low_rank_vs_full_rank']):
        if a['rank']!=cfg['n']:assert a==b
    assert original['requirements']==corrected['requirements']
    correction=dict(reason='Full-rank dense and truncated share the same data, policy and interruption costs. Their ratio is identically1, including all bootstrap draws. Independent numerator/denominator interval extrema were unnecessarily loose for this identity.',
        only_changed_fields=fields,only_changed_rank=cfg['n'],source_execution_audit_sha256=sha(source/'execution_cost_audit.json'),
        original_archive_manifest_sha256=archive['manifest_sha256'],raw_data_and_other_rank_results_preserved=True,
        changed=changed,review_job=os.environ['SLURM_JOB_ID'])
    corrected['self_comparison_correction']=correction
    (dest/'execution_cost_audit.json').write_text(json.dumps(corrected,indent=2)+'\n',encoding='utf-8')
    summary=read(dest/'summary.json');summary['execution_cost_accounting']=corrected;summary['review_correction']=correction
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    path=dest/'executed_low_rank_vs_full_rank.csv'
    with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    names=list(rows[0])
    for q in rows:
        if int(q['rank'])==cfg['n']:
            for key in fields:q[key]='1.0'
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(rows)
    html=(dest/'results.html').read_text(encoding='utf-8')
    for old,new in zip(original['low_rank_vs_full_rank'],corrected['low_rank_vs_full_rank']):
        if old['rank']!=cfg['n']:continue
        needle=html_row(old);assert html.count(needle)==1,(old['relative_target'],needle)
        html=html.replace(needle,html_row(new))
    note='<p><strong>修正版：</strong>full-rank 两方法共享同一轨迹、策略和中断成本，自比较收益恒等于1。其他rank及全部样本量保持原值。<a href="correction_provenance.json">修正依据与原始归档校验</a>。</p>'
    html=html.replace('<table><tr><th>Rank</th>',note+'<table><tr><th>Rank</th>',1)
    (dest/'results.html').write_text(html,encoding='utf-8')
    (dest/'correction_provenance.json').write_text(json.dumps(correction,indent=2)+'\n',encoding='utf-8')
    sources=dest/'review_sources';sources.mkdir()
    root=Path(__file__).resolve().parents[1]
    for name in ['scripts/review_ce500_random_a_identity.py','scripts/ce500_random_a_execution_audit_v5.py']:
        shutil.copyfile(root/name,sources/Path(name).name)
    manifest={str(path.relative_to(dest)):sha(path) for path in dest.rglob('*') if path.is_file()}
    (dest/'review_sha256.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='PASS',review=str(dest),files=len(manifest),self_comparison_exactly_one=True,
        all_other_rank_results_unchanged=True,source_manifest_sha256=archive['manifest_sha256'])))


if __name__=='__main__':main()
