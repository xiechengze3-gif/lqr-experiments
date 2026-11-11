"""Render the sealed X14 readouts and ledger as Markdown."""
import argparse
import csv
import json
import math
from pathlib import Path


R=Path(__file__).resolve().parent
ALGORITHMS=('NPG','PI')


def table(path):
    with path.open(newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def read(path):
    return json.loads(path.read_bytes())


def number(value):
    if value in ('',None):
        return '—'
    value=float(value)
    return '∞' if value==math.inf else f'{value:.4g}'


def interval(row,keys):
    med,lo,hi=(number(row[k]) for k in keys)
    return f'{med} [{lo}, {hi}]' if med!='—' else med


def j(row):
    return round(-math.log2(float(row['rung'])))


def label(row):
    if not row['ci_low'] or not row['ci_high']:
        return 'unavailable'
    if float(row['ci_low'])>1:
        return 'above 1'
    if float(row['ci_high'])<1:
        return 'below 1'
    return 'contains 1'


def markdown_table(lines,header,rows):
    lines.extend(('', '| '+' | '.join(header)+' |', '| '+' | '.join(['---']*len(header))+' |'))
    lines.extend('| '+' | '.join(map(str,row))+' |' for row in rows)
    lines.append('')


def actor_tables(lines,rows):
    by={(float(r['alpha']),r['algorithm'],j(r),r['ratio_kind']):r for r in rows}
    assert len(by)==len(rows)
    alphas=sorted({key[0] for key in by})
    primary=[]
    ratio_keys=('paired_ratio_median','ci_low','ci_high')
    for alpha in alphas:
        for alg in ALGORITHMS:
            row=by[alpha,alg,0,'both_stable']
            primary.append((alpha,alg,row['both_stable']+'/32',interval(row,ratio_keys),label(row)))
    lines.extend(('## Largest registered budget',''))
    markdown_table(lines,['α','Algorithm','Both stable','Dense / truncated [95% CI]','Interval vs 1'],primary)
    lines.extend(('## Nine-rung paired comparisons','',
        'Budgets are indexed by j in Ncal / 2^j. Primitive transitions are per arm and include burn-in and baseline. '
        'Gap cells show median [Q1, Q3]. Ratio cells show the median with the registered 95% system-cluster interval. '
        'Stable counts use all 32 pairs. Infinity represents failed outputs.'))
    for alpha in alphas:
        for alg in ALGORITHMS:
            lines.extend(('',f'### α = {alpha:g}, {alg}'))
            cells=[]
            classes={name:[] for name in ('above 1','below 1','contains 1','unavailable')}
            for rung in range(9):
                both=by[alpha,alg,rung,'both_stable']
                full=by[alpha,alg,rung,'failure_inclusive']
                classes[label(both)].append(rung)
                gaps=[interval(both,tuple(f'{arm}_{metric}_{suffix}' for suffix in ('median','q25','q75')))
                      for metric in ('gap','relative_gap') for arm in ('dense','truncated')]
                cells.append((rung,int(float(both['primitive_per_arm'])),*gaps,
                              f"{both['dense_stable']} / {both['truncated_stable']} / {both['both_stable']}",
                              interval(both,ratio_keys),interval(full,ratio_keys)))
            markdown_table(lines,['j','Transitions','Dense gap','Truncated gap','Dense relative gap',
               'Truncated relative gap','Stable D / T / both','Both-stable ratio','Failure-inclusive ratio'],cells)
            for name,values in classes.items():
                lines.append(f"- {name.capitalize()} at j = {', '.join(map(str,values)) if values else 'none'}.")
            lines.append('')


def ledger(lines,seal):
    books=seal['accounting']
    rows=[]
    for entry in books['jobs']:
        actual=sum(row['elapsed_seconds']*row['billing']/3600 for row in entry['allocations'])
        rows.append((entry['item'],entry['stage'],entry['job'],entry['tasks'],entry['minutes'],
                     f'{actual:.6f}',f"{entry['tasks']*entry['minutes']/60:.6f}",f"{entry['exposure_SU']:.6f}"))
    lines.extend(('## Grace ledger',''))
    markdown_table(lines,['Item','Stage','Job','Allocations','Wall limit (min)','Actual SU','Requested upper SU','Exposure at submission SU'],rows)
    lines.extend((f"Settled actual {books['settled_SU']:.6f} SU. Outstanding upper {books['outstanding_upper_SU']:.6f} SU. "
                  f"Exposure including the 4 SU report reserve {books['settled_SU']+books['outstanding_upper_SU']+4:.6f} SU. "
                  f"Historical sum of requests {books['historical_requested_SU']:.6f} SU includes released reservations.",''))


def build(mode):
    lines=['# X14a report' if mode=='a' else '# X14 experiment report','',
        'Family S, n = m = 24, K0 = 0, order-2 truncation, H = 16, exploration variance 1 and '
        '16 burn blocks plus one baseline per stage. NPG uses 16 updates with η = 0.2 and PI uses eight '
        'full greedy updates with PSD projection and joint compression. All cells use eight systems and four paired seeds.',
        '', 'The preregistered α = 0.02 cell has full-rank B and tail energy 0.0088 at k = 2. '
        'This is within the 0.01 tail-energy criterion. Gap and stability observations are descriptive, '
        'and the pilot calibration does not certify the theorem’s sufficient sampling bounds.']
    if mode=='a':
        folder=R/'delivery-a-report'
        actor_tables(lines,table(folder/'summary.csv'))
        ledger(lines,read(folder/'SEAL.json'))
        output=R/'X14a_REPORT_v1.md'
    else:
        actor_tables(lines,table(R/'X9_summary_merged_nine_rungs.csv'))
        lines.extend(('## n = 60 PI calibration',''))
        cal=table(R/'PI_calibration_n60.csv')
        markdown_table(lines,['Estimate','Selected blocks','Status','Exceeds X12 Ncal'],
            [(r['algorithm'],r['smallest_N'] or f"> {r['censored_above_N']}",r['status'],r['exceeds_X12_N_cal']) for r in cal])
        lines.extend(('## n = 60 fixed-gain estimator error',''))
        accuracy=table(R/'estimate_accuracy_n60.csv')
        markdown_table(lines,['Estimate','Arm','Blocks or transitions before burn-in','Relative Frobenius error [IQR]','Paired D / T [IQR]'],
            [(r['algorithm'],r['arm'],r['N'],interval(r,('relative_error_median','relative_error_q25','relative_error_q75')),
              interval(r,('paired_error_ratio_median','paired_error_ratio_q25','paired_error_ratio_q75'))) for r in accuracy])
        lines.extend(('## n = 60 CE gaps','',
                      'All readouts use the X10a saved fits and endpoint gaps from the same nested prefixes.'))
        ce=table(R/'CE_ratio_n60.csv')
        markdown_table(lines,['N','Dense stable','Truncated stable','Both stable','Dense / truncated [95% CI]'],
            [(r['N'],r['dense_stable'],r['truncated_stable'],r['both_stable'],
              interval(r,('paired_ratio_median','ci_low','ci_high'))) for r in ce])
        ledger(lines,read(R/'delivery-d-report/SEAL.json'))
        lines.extend(('## Scope and paper checks','', (R/'PAPER_CHECK_v1.md').read_text(encoding='utf-8').strip(),''))
        output=R/'REPORT.md'
    with output.open('x',encoding='utf-8',newline='\n') as f:
        f.write('\n'.join(lines)+'\n')
    print(output.name)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['a','final'])
    build(parser.parse_args().mode)
