"""Publish and format frozen compute-node CSVs. No numerical analysis runs here."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'delivery-report-v1/report-v1/summary'
EXPECTED = {'all_records.csv':10752, 'summary.csv':336,
    'paired_ratios.csv':624, 'paired_records.csv':9984,
    'adaptive_orders.csv':96, 'posthoc_best_fixed.csv':24,
    'log_slopes.csv':224, 'model_certificates.csv':32, 'spectral_tails.csv':1184}
SOURCES = {'frozen_engine.py':'9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989',
    'ce_fullrank.py':'8354be2fa64874c811dffe1aa3c367f78e125389d53f357c59a453b734af5fc4',
    'analyze_ce.py':'5f195e95ae91c5b5d9a8580e7f067783572f2376f368179abb7c2feda9525763',
    'x7_driver.py':'0a284a28e13b67ee48eaaf82af209afbdcaa6cd1666c6a6916666ddfeb033cbb'}

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:return list(csv.DictReader(f))
def fmt(value):
    if value in ('', None):return 'NA'
    if str(value).lower() in ('inf','infinity'):return '∞'
    return format(float(value), '.4g')
def fresh(path, data):
    assert not path.exists(), f'Preserve existing {path}'
    path.write_bytes(data)
def table(headers, data):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |']+
        ['| '+' | '.join(map(str,r))+' |' for r in data])+'\n'

def main():
    proof=json.loads((SOURCE/'verification.json').read_text())
    assert proof['status']=='COMPLETE' and proof['zero_new_transitions']
    assert proof['config_sha256']==digest(ROOT/'prepared-formal-v1/formal-config.json')
    for name,expected in SOURCES.items():assert digest(ROOT/name)==expected
    counts={}
    for name,count in EXPECTED.items():
        assert digest(SOURCE/name)==proof['files'][name]
        counts[name]=len(rows(SOURCE/name));assert counts[name]==count
        fresh(ROOT/name,(SOURCE/name).read_bytes())
    fresh(ROOT/'summary-verification.json',(SOURCE/'verification.json').read_bytes())
    summaries=rows(ROOT/'summary.csv'); ratios=rows(ROOT/'paired_ratios.csv')
    summary={(r['n'],r['spectrum'],r['N'],r['mode']):r for r in summaries}
    ratio={(r['n'],r['spectrum'],r['N'],r['mode'],r['ratio_kind']):r for r in ratios}
    assert len(summary)==336 and len(ratio)==624
    assert all(r['full']=='32' for r in summaries)
    per_arm=[]
    for r in summaries:
        per_arm.append([r['n'],r['spectrum'],r['N'],r['transitions'],r['mode'],r['stable']+'/32',
            fmt(r['gap_median']),f"[{fmt(r['gap_q25'])}, {fmt(r['gap_q75'])}]",
            fmt(r['relative_gap_median']),f"[{fmt(r['relative_gap_q25'])}, {fmt(r['relative_gap_q75'])}]",
            fmt(r['order_median']),r['chosen_zero']])
    fresh(ROOT/'PER_ARM_TABLE.md', ('# X7 full registered coverage\n\nAll entries are formatted from summary.csv; '+
        'failure-inclusive statistics over all 32 runs. N excludes burn-in; transitions=N+512. '+
        'Sensitivities are not selection rules. No statistics are recomputed locally.\n\n'+
        table(['n','Spectrum','N','N+512','Arm','Stable','Gap median','Gap IQR',
               'Relative median','Relative IQR','Order median','Order=0'],per_arm)).encode())
    blocks=['# X7 compact saved-CSV tables\n\nRatios are medians of paired dense/arm gaps, '+
        'with 5,000 common-draw system-cluster bootstrap samples; 95% pointwise intervals. '+
        'Post hoc best fixed minimizes the full-32 median absolute gap and includes dense; '+
        'its interval is descriptive and does not adjust for selecting the order.\n']
    compact=[]
    for best in rows(ROOT/'posthoc_best_fixed.csv'):
        key=(best['n'],best['spectrum'],best['N']);dense=summary[key+('dense',)]
        out=[*key,best['best_fixed_k'],fmt(dense['relative_gap_median'])]
        for mode in [best['best_fixed_mode'],'adaptive_paper','adaptive_split','sensitivity_C0p5','sensitivity_C1p0']:
            arm=summary[key+(mode,)]
            if mode=='dense':effect='1 (self)'
            else:
                rr=ratio[key+(mode,'failure_inclusive')]
                effect=f"{fmt(rr['paired_ratio_median'])} [{fmt(rr['ci_low'])}, {fmt(rr['ci_high'])}]"
            out.append(f"{fmt(arm['relative_gap_median'])}; {effect}")
        compact.append(out)
    blocks.append(table(['n','Spectrum','N','Post hoc k','Dense relative gap',
        'Post hoc relative gap; ratio [CI]','Paper relative gap; ratio [CI]',
        'Split relative gap; ratio [CI]','Sensitivity C=.5 relative gap; ratio [CI]',
        'Sensitivity C=1 relative gap; ratio [CI]'],compact))
    blocks.append('\n## Adaptive order (median [IQR]; zero count)\n\n')
    order_rows=[]
    for r in rows(ROOT/'adaptive_orders.csv'):
        order_rows.append([r['n'],r['spectrum'],r['N'],r['mode'],
            f"{fmt(r['k_median'])} [{fmt(r['k_q25'])}, {fmt(r['k_q75'])}]",r['zero_order'],
            fmt(r['threshold_median'])])
    blocks.append(table(['n','Spectrum','N','Rule','Order','Zero/32','Threshold median'],order_rows))
    blocks.append('\n## Registered slopes, all arms\n\nIntervals condition on finite-positive '+
        'bootstrap medians; unidentified repetitions are retained separately.\n\n')
    slope_rows=[]
    for r in rows(ROOT/'log_slopes.csv'):
        slope_rows.append([r['n'],r['spectrum'],r['mode'],r['metric'],r['window'],
            fmt(r['log_gap_log_N_slope']),f"[{fmt(r['bootstrap_ci_low'])}, {fmt(r['bootstrap_ci_high'])}]",
            r['bootstrap_unidentified']+'/5000'])
    blocks.append(table(['n','Spectrum','Arm','Metric','Window','Slope','Conditional 95% CI','Unidentified'],slope_rows))
    fresh(ROOT/'RESULT_TABLES.md','\n'.join(blocks).encode())
    output={'status':'PUBLISHED_EXACT_BYTES','counts':counts,'files':proof['files'],
        'frozen_sources':SOURCES,'local_scope':'Hash, CSV coverage and formatting only; no numerical analysis'}
    fresh(ROOT/'PUBLICATION_CHECK_v1.json',(json.dumps(output,indent=2)+'\n').encode())
    print(json.dumps(output))

if __name__=='__main__':main()
