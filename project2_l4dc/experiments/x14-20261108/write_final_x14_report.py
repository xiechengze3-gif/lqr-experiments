"""Assemble the two sealed X14 books and complete scientific readouts."""
from write_x14_report import R, actor_tables, interval, j, ledger, markdown_table, number, read, table


RATIO=('paired_ratio_median','ci_low','ci_high')


def gap(row,arm,metric='gap'):
    return interval(row,tuple(f'{arm}_{metric}_{suffix}' for suffix in ('median','q25','q75')))


def bstar(lines):
    out=R/'delivery-f-full-report'
    table_rows=table(out/'B60_summary.csv')
    by={(r['algorithm'],j(r),r['ratio_kind']):r for r in table_rows}
    assert len(by)==36
    lines.extend(('## n = m = 60 at the B* budget ladder','',
                  'B* = 3,276,800 blocks, or 455.11 blocks per unit of n(n+m). '
                  'This post-hoc budget is 1.5625 times the X12 calibration base. '
                  'Both arms use the same primitive transitions. All systems, seeds and learner settings are from X12.'))
    for alg in ('NPG','PI'):
        cells=[]
        for i in range(9):
            r=by[alg,i,'both_stable']
            all_pairs=by[alg,i,'failure_inclusive']
            cells.append((i,int(float(r['primitive_per_arm'])),gap(r,'dense'),gap(r,'truncated'),
                          gap(r,'dense','relative_gap'),gap(r,'truncated','relative_gap'),
                          f"{r['dense_stable']} / {r['truncated_stable']} / {r['both_stable']}",
                          interval(r,RATIO),interval(all_pairs,RATIO)))
        lines.extend(('',f'### {alg}'))
        markdown_table(lines,['j','Transitions','Dense gap','Truncated gap','Dense relative gap','Truncated relative gap',
                              'Stable D / T / both','Both-stable ratio','Failure-inclusive ratio'],cells)
    top=table(R/'delivery-f-report/X14f_summary.csv')
    markdown_table(lines,['Algorithm','Top dense median D / gap','Dense and truncated stable'],
                   [(r['algorithm'],number(r['dense_D_over_gap_median']),f"{r['dense_stable']} / {r['truncated_stable']}")
                    for r in top if r['ratio_kind']=='both_stable'])
    lines.extend(('### Matching the dense top-rung median gap',''))
    crossings=[]
    for name,path in [('Nine B* rungs',out/'B60_transitions_saved.csv'),
                      ('Original nine X12 rungs plus B*',R/'delivery-f-report/X14f_transitions_saved_derived.csv')]:
        for r in table(path):
            flags=' / '.join(flag.replace('_',' ') for flag in ('left_censored','right_censored','unbracketed') if r[flag]=='True')
            crossings.append((name,r['algorithm'],number(r['dense_gap_at_N_cal']),number(r['truncated_N_to_match']),
                              number(r['factor']),flags or ('bracketed' if r['target_identified']=='True' else 'unidentified target')))
    markdown_table(lines,['Curve','Algorithm','Target gap','Matched transitions','Transition ratio','Censoring'],crossings)
    lines.extend(('The replacement tables preserve all 144 non-60 summary rows and all eight non-60 crossing rows byte for byte. '
                  'The X12 calibration-base n = 60 results remain available in the original files.',''))


def estimate_and_ce(lines):
    lines.extend(('## n = 60 pilot calibration','',
                  'The criterion uses the median of two system medians, with four seeds per system. '
                  'A value of at most one for the normalized operator error qualifies. The B* check uses the same eight pilot streams.'))
    cal=table(R/'PI_calibration_n60.csv')
    markdown_table(lines,['Estimate','Original grid selection','Exceeds X12 Ncal','Normalized error at B*','Qualifies at B*'],
                   [(r['algorithm'],r['smallest_N'] or f"> {r['censored_above_N']}",r['exceeds_X12_N_cal'],
                     number(r['Bstar_rho_op_median']),r['Bstar_qualifies']) for r in cal])
    lines.extend(('## n = 60 estimator error at K0','',
                  'NPG and PI use the same 2^22-block Stein record. CE uses 2^19 transitions with burn-in counted separately.'))
    accuracy=table(R/'estimate_accuracy_n60.csv')
    markdown_table(lines,['Estimate','Arm','Blocks or transitions before burn-in','Relative Frobenius error [IQR]','Paired D / T [IQR]'],
                   [(r['algorithm'],r['arm'],r['N'],interval(r,('relative_error_median','relative_error_q25','relative_error_q75')),
                     interval(r,('paired_error_ratio_median','paired_error_ratio_q25','paired_error_ratio_q75'))) for r in accuracy])
    lines.extend(('## n = 60 CE gap ratios','',
                  'The X10a saved paired gaps and fit hashes cover all five rungs. Reanalysis generated zero new observations.'))
    ce=table(R/'CE_ratio_n60.csv')
    markdown_table(lines,['N','Dense stable','Truncated stable','Both stable','Dense / truncated [95% CI]'],
                   [(r['N'],r['dense_stable'],r['truncated_stable'],r['both_stable'],interval(r,RATIO)) for r in ce])


def main():
    lines=['# X14 experiment report','',
           'All actor comparisons use eight family-S systems and four paired seeds, '
           'K0 = 0, rank-2 truncation, H = 16 and 17 burn-in and baseline blocks per stage. '
           'Stein NPG uses 16 updates at η = 0.2. PI uses eight full greedy updates and PSD projection with joint compression.',
           '', 'The preregistered α = 0.02 cell has full-rank B and squared tail energy 0.0088 at k = 2, '
           'within the 0.01 tail-energy criterion. Reported intervals describe paired gap ratios.']
    actor_tables(lines,table(R/'X9_summary_merged_nine_rungs.csv'))
    bstar(lines)
    estimate_and_ce(lines)
    for name,folder in [('X14a–e','delivery-d-report'),('X14f and its extension','delivery-f-full-report')]:
        entry=[]
        ledger(entry,read(R/folder/'SEAL.json'))
        entry[0]=f'## Grace ledger for {name}'
        lines.extend(entry)
    lines.extend(('## Scope and paper checks','',(R/'PAPER_CHECK_v1.md').read_text(encoding='utf-8').strip(),''))
    with (R/'REPORT.md').open('x',encoding='utf-8',newline='\n') as f:
        f.write('\n'.join(lines)+'\n')
    print('REPORT.md')


if __name__=='__main__':
    main()
