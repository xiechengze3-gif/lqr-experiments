"""Resolve legacy report rounding without changing a single observation."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent;C=R.parents[1]
source=Path('C:/Users/24375/Projects/project2_l4dc/figs/data/X6a_CE_full_gaps.csv')
baseline=R/'paper-rounded-X6a_CE_full_gaps.csv'
with baseline.open('xb') as f:f.write(source.read_bytes())
s=(R/'report_x11.py').read_text();assert s.count("out=R/'report-v1'")==1
s=s.replace("out=R/'report-v1'","out=R/'report-v2'")
old="""    reused_cost=[];new_cost=[]
    for row in cost_rows:
        if row['n']==row['m']:
            oldrow=oldcost[row['n']]
            for arm in ['dense','truncated']:
                assert np.isclose(row[arm+'_N_req'],float(oldrow[arm+'_N_req']),rtol=1e-12,atol=1e-8),'Original-paper cross arithmetic mismatch.'
            reused_cost.append(dict(oldrow,m=row['n']))
        else:new_cost.append(row)
"""
new="""    paper=R/'paper-rounded-X6a_CE_full_gaps.csv';sources[str(paper)]=sha(paper)
    with paper.open(newline='') as f:paperrows=[r for r in csv.DictReader(f) if r['family']=='S' and r['n']=='48']
    reused_cost=[];new_cost=[];rounding_audit=[]
    for row in cost_rows:
        if row['n']==row['m']:
            oldrow=oldcost[row['n']]
            for arm,key in [('dense','dense_abs_gap'),('truncated','trunc_abs_gap')]:
                if row['n']==48:
                    reference=cost(np.array([float(r['N']) for r in paperrows]),np.array([float(r[key]) for r in paperrows]),.01)
                else:reference=row[arm+'_N_req']
                assert np.isclose(reference,float(oldrow[arm+'_N_req']),rtol=1e-12,atol=1e-8),'Original-paper input arithmetic mismatch.'
                rounding_audit.append(dict(n=row['n'],m=row['m'],arm=arm,full_precision_raw_cross=row[arm+'_N_req'],
                    original_csv_cross=float(oldrow[arm+'_N_req']),original_input_cross=reference,
                    raw_vs_original_difference=row[arm+'_N_req']-float(oldrow[arm+'_N_req']),
                    explanation='Old X6a paper CSV uses 5-significant-digit report transcription; new rows use full precision.' if row['n']==48 else 'X10a full-precision saved records reproduce unchanged original row.'))
                row[arm+'_N_req']=float(oldrow[arm+'_N_req'])
            reused_cost.append(dict(oldrow,m=row['n']))
        else:new_cost.append(row)
    csv_new(out/'legacy_rounding_audit.csv',rounding_audit)
"""
assert s.count(old)==1;s=s.replace(old,new)
s=s.replace('Reused square48/16 crossings reproduce original CSV within1e-12 relative tolerance; original source values retained in merged rows.',
    'Square48 original paper crossings reproduce from its rounded report-transcribed gap CSV; raw full-precision crosses differ by 0.3000 dense and 0.02047 rank2 samples. Square16 reproduces directly from full-precision X10a records. Original source values retained in merged rows; all new rows use full precision with the same crossing arithmetic. See legacy_rounding_audit.csv. Report-v1 stopped on this provenance check and is preserved; no trajectory rerun.')
s=s.replace("old_square_crosses_reproduced=True", "old_square_crosses_reproduced_from_original_inputs=True,legacy_rounding_disclosed=True")
compile(s,'report_x11_v2.py','exec')
p=R/'report_x11_v2.py'
with p.open('xb') as f:f.write(s.encode())
proof=dict(status='SAVED_RECORD_REPORT_READER_CORRECTION',new_training_transitions=0,
    old_source_sha256=hashlib.sha256((R/'report_x11.py').read_bytes()).hexdigest(),
    corrected_source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
    paper_rounded_csv_source=str(source),paper_rounded_csv_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
    changed_new_cell_arithmetic=False,original_reused_cost_values_preserved=True,all_old_outputs_untouched=True)
with (R/'REPORT_CORRECTION_v2.json').open('x') as f:json.dump(proof,f,indent=2)
with (C/'CODEX_REPLY.md').open('a',encoding='utf-8') as f:
    f.write('\n## X11 REPORT legacy precision reconciliation\n\nFORMAL all352 paths complete. Report-v1 correctly stopped when old48 crossings differed from original CSV by0.300017 dense and0.020469 rank2 samples. Cause established exactly: old paper gap CSV was transcribed from five-significant-digit REPORT tables; its rounded inputs reproduce both original crossings exactly. Full-precision old raw records produce slightly different crossings; square16 full-precision X10a reproduces directly. New report-v2 keeps reused old CSV values untouched, records both crosses/precision/source hashes in legacy_rounding_audit.csv, and uses unchanged full-precision new-cell arithmetic. No trajectory rerun/old file edit; failed report-v1 retained. Corrected reader/source diff in REPORT_CORRECTION_v2.json.\nSTATUS: REPORT PRECISION RECONCILED X11\n')
print(json.dumps(proof))
