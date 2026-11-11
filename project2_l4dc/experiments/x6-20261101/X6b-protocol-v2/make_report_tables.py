"""Format hash-verified saved CSVs only; no statistical or model recomputation."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'X6b-report-v1'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(name):
    with (OUT/(name+'.csv')).open(newline='',encoding='utf-8') as stream:return list(csv.DictReader(stream))
def fmt(value):
    if value is None or value=='':return 'NA'
    try:
        number=float(value)
        if math.isinf(number):return '∞' if number>0 else '-∞'
        if math.isnan(number):return 'NA'
        return f'{number:.6g}'
    except ValueError:return value
def rung(value):return {1/64:'1/64',1/16:'1/16',1/4:'1/4',1.:'1'}[float(value)]
def ci(row,key='paired_ratio_median',lo='ci_low',hi='ci_high'):
    return f"{fmt(row[key])} [{fmt(row[lo])}, {fmt(row[hi])}]"
def table(headers,rows):
    return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|']+
        ['|'+'|'.join(str(x) for x in row)+'|' for row in rows])+'\n'
def write(name,body): 
    path=OUT/'tables'/name
    assert not path.exists()
    path.write_text(body,encoding='utf-8')

def main():
    proof=json.loads((OUT/'verification.json').read_text())
    assert proof['status']=='COMPLETE'
    assert proof['source_sha256']=='ec27555202189295f5d46db3c4d51684e1344db58ffea44eb3acd9965bb55469'
    for name,value in proof['files'].items():assert sha(OUT/name)==value,name
    summaries=read('summary');cells=[r for r in summaries if r['ratio_kind']=='both_stable']
    attainment=read('attainment');diagnostics=read('diagnostic_summary')
    assert len(summaries)==64 and len(cells)==32 and len(attainment)==32
    (OUT/'tables').mkdir()
    body='# Per-rung terminal gaps\n\nFull32 failure-inclusive medians and IQRs. Failed endpoint gap=∞. Each displayed cell is copied from summary.csv; the ratio_kind choice removes duplicated gap columns and does not condition these gap summaries on stability. All primitive transitions include burn/baseline and absorbing-failure padding. D/T=stable counts out of32.\n'
    for metric in ['gap','relative_gap']:
        body+='\n## '+metric+'\n\n'
        body+=table(['n','algorithm','rung','M per arm','D/T stable','dense median [Q25,Q75]','truncated median [Q25,Q75]'],[
            [r['n'],r['algorithm'],rung(r['rung']),r['primitive_per_arm'],r['dense_stable']+'/'+r['truncated_stable'],
             ci(r,'dense_'+metric+'_median','dense_'+metric+'_q25','dense_'+metric+'_q75'),
             ci(r,'truncated_'+metric+'_median','truncated_'+metric+'_q25','truncated_'+metric+'_q75')] for r in cells])
    write('per-rung-gaps.md',body)
    write('paired-ratios.md','# Paired terminal gap ratios\n\nRatio=g(dense)/g(truncated), taken per pair before the median. Both-stable and failure-inclusive definitions are both retained. Failure-inclusive uses one-sided failures as0/∞,dropping only both-failed pairs. CI=5000 system-cluster bootstrap draws over8 systems with4 seeds each; common draws within(n,algorithm) across all rungs/arms/epsilon/ratio definitions. Empty conditional resamples are reported and excluded from that conditional percentile; no finite cap is substituted for infinity. These are pointwise CIs.\n\n'+
        table(['n','algorithm','rung','definition','D/T stable','pairs/32','median [95%CI]','invalid BS/5000','both failed'],[
            [r['n'],r['algorithm'],rung(r['rung']),r['ratio_kind'],r['dense_stable']+'/'+r['truncated_stable'],r['ratio_pairs'],ci(r),r['bootstrap_invalid'],r['both_failed']] for r in summaries]))
    write('observed-epsilon.md','# Observed budget-to-epsilon\n\nSuccess means relative gap<=epsilon; the criterion is>=29/32. Rung order is[1/64,1/16,1/4,1]. A >M entry means right-censored above the maximum tested M; it is not an identified minimum at an unobserved budget. CIs and censored bootstrap mass are copied from attainment.csv. No interpolation or population-success guarantee.\n\n'+
        table(['n','algorithm','arm','epsilon','observed minimum / censor','successes by rung','95% bootstrap CI','censored BS/5000'],[
            [r['n'],r['algorithm'],r['arm'],r['relative_epsilon'],
             ('>'+r['censored_above']) if r['status']=='RIGHT_CENSORED' else r['smallest_observed_budget'],
             r['successes_by_rung'],f"[{fmt(r['bootstrap_ci_low'])}, {fmt(r['bootstrap_ci_high'])}]",r['bootstrap_censored']] for r in attainment]))
    diagrows=[]
    for c in cells:
        stage=16 if c['algorithm']=='NPG' else 8
        for arm in ['dense','truncated']:
            label='NPG_applied' if c['algorithm']=='NPG' else ('PI_clipped' if arm=='dense' else 'PI_joint_compressed')
            matches=[r for r in diagnostics if int(float(r['n']))==int(c['n']) and r['algorithm']==c['algorithm']
                     and float(r['rung'])==float(c['rung']) and r['arm']==arm and int(float(r['stage']))==stage and r['diagnostic']==label]
            assert len(matches)<=1
            r=matches[0] if matches else {}
            diagrows.append([c['n'],c['algorithm'],rung(c['rung']),arm,stage,label,r.get('eligible','0')+'/32',
                fmt(r.get('rho_op_median')),fmt(r.get('relative_error_median')),fmt(r.get('projection_median')),
                fmt(r.get('projection_mean_of_available_system_means'))+' ± '+fmt(r.get('projection_system_se'))])
    write('terminal-path-diagnostics.md','# Last-update path diagnostics\n\nTargets are computed at each arm own PRE-update policy: NPG target Z, PI target[G,Z]. rho_op=operator error/sigma_2(target); relative error=Frobenius error/target Frobenius norm; projection=<estimate,target>/||target||_F^2. These are not relative errors in RK+Z. Dense PI learner applies PI_clipped, truncated PI applies PI_joint_compressed. Other variants in diagnostic_summary.csv are counterfactual diagnostics on the same arm, not extra learners. Padding is not an update and is NA, never recovery. The stage field is the update number; diagnostic_policy_stage=stage-1. Eligibility is retained over all32 paths, not selected by post-update survival. System mean±SE uses available systems as saved; the projection median is a distinct statistic.\n\n'+
        table(['n','algorithm','rung','arm','update','learner estimate','eligible','rho_op median','relative Frob median','projection median','system projection mean±SE'],diagrows))
    write('endpoint-decomposition.md','# Terminal gap decomposition\n\nFor stable endpoints only,the saved simulator checks g(K)=D(K)+g(Pi K),with B(K-Pi K)=0. D is the null-action control cost; action_gap is the gap of the projected gain. Eligibility is explicit. Medians of the summands need not sum to the median total. This is post-update endpoint analysis; the path diagnostics use the previous policy.\n\n'+
        table(['n','algorithm','rung','arm','eligible/32','median D','median action gap','median D/g','median action error Frob'],[
            [r['n'],r['algorithm'],rung(r['rung']),arm,r[arm+'_D_eligible'],
             fmt(r[arm+'_D_median']),fmt(r[arm+'_action_gap_median']),fmt(r[arm+'_D_over_gap_median']),fmt(r[arm+'_action_error_fro_median'])]
            for r in cells for arm in ['dense','truncated']]))
    result=dict(status='SAVED_CSV_FORMATTING_ONLY',source_sha256=sha(Path(__file__)),
        numerical_inputs=proof['files'],tables={p.name:sha(p) for p in (OUT/'tables').glob('*.md')})
    (OUT/'table-manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
