"""Review03:30: all initialization variants and exact first-failure counts, saved CSV only."""
import csv,json
from collections import defaultdict
from control import ROOT,review,sha,append

def read(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

review();old=ROOT/'X1/report-actors';dest=ROOT/'X1/report-actors-full-tables-v2';assert not dest.exists();dest.mkdir()
stats=read(old/'endpoint_statistics.csv');effects=read(old/'paired_bootstrap_effects.csv');raw=read(old/'all_recorded_iterates.csv')
key=lambda r:(r['algorithm'],r['m'],r['null_scale'],r['mode'])
relative={key(r):r for r in stats if r['metric']=='relative_gap'}
paired={(r['algorithm'],r['m'],r['null_scale']):r for r in effects};full=[]
for g in stats:
    if g['metric']!='gap':continue
    rel=relative[key(g)];p=paired[(g['algorithm'],g['m'],g['null_scale'])]
    row=dict(null_scale=g['null_scale'],m=g['m'],m_minus_r=int(g['m'])-2,algorithm=g['algorithm'],mode=g['mode'],
      gap_median=g['median'],gap_q25=g['q25'],gap_q75=g['q75'],relative_gap_median=rel['median'],relative_gap_q25=rel['q25'],relative_gap_q75=rel['q75'],
      stable_count=g['stable_count'],denominator=32,failed_count=g['failures'],planned_M=g['planned_transitions'],padding_transitions_total=g['padding_transitions_total'],
      finite_paired_count=p['finite_pairs'],paired_denominator=32,dense_over_truncated_median=p['paired_ratio_median'],
      paired95_low=p['bootstrap95_low'],paired95_high=p['bootstrap95_high'])
    full.append(row)
assert len(full)==36;write(dest/'all_null_variants_endpoint_table.csv',full)
updates=defaultdict(list);paths=defaultdict(list)
for r in raw:
    updates[(r['algorithm'],r['null_scale'],int(r['m']),r['mode'],int(r['stage']))].append(r)
    paths[(r['algorithm'],r['null_scale'],int(r['m']),r['mode'],r['system'],r['trial'])].append(r)
update_rows=[]
for k,rows in sorted(updates.items()):
    assert len(rows)==32
    update_rows.append(dict(algorithm=k[0],null_scale=k[1],m=k[2],m_minus_r=k[2]-2,mode=k[3],stage=k[4],
       stable_count=sum(r['stable']=='True' for r in rows),denominator=32,failed_count=sum(r['stable']=='False' for r in rows),
       actual_M_min=min(int(r['transitions']) for r in rows),actual_M_max=max(int(r['transitions']) for r in rows),
       cumulative_padding_total=sum(int(r['padding_transitions']) for r in rows)))
write(dest/'failure_by_update.csv',update_rows);first=[]
for k,rows in sorted(paths.items()):
    bad=sorted(int(r['stage']) for r in rows if r['stable']=='False')
    first.append(dict(algorithm=k[0],null_scale=k[1],m=k[2],m_minus_r=k[2]-2,mode=k[3],system=k[4],trial=k[5],
       first_failed_update=bad[0] if bad else None,failed_endpoint=bool(bad),planned_denominator_per_cell=32))
assert len(first)==1152;write(dest/'first_failure_by_system_seed.csv',first)
source_hashes={p.name:sha(p) for p in [old/'endpoint_statistics.csv',old/'paired_bootstrap_effects.csv',old/'all_recorded_iterates.csv']}
(dest/'REPORT.json').write_bytes((json.dumps(dict(status='COMPLETE',endpoint_rows=36,update_rows=len(update_rows),
       trajectories=1152,failed_endpoints=sum(r['failed_endpoint'] for r in first),source_hashes=source_hashes,
       code_sha256=sha(__file__),new_learning_runs=0,provenance='Local standard-library saved-CSV aggregation'),indent=2)+'\n').encode())
body='Scope: X1 actor Review03:30 complete per-null/per-redundancy table, saved-data only.\n\n'
body+='`X1/report-actors-full-tables-v2/all_null_variants_endpoint_table.csv` has all36(algorithm,null,m,method) cells, including m=r zero-null baseline, both initialization variants, failure-inclusive absolute/relative medians/IQR, stable/full32 counts, actual padding totals, and finite-pair/full32 counts beside each paired bootstrap interval. `failure_by_update.csv` gives every iterate/cell failure count; `first_failure_by_system_seed.csv` retains all1152 trajectories, including193 failed PI endpoints.\n\n'
body+='| null | m-r | Algorithm | Method | Gap median [IQR] | Relative median [IQR] | Stable | Finite pairs | Dense/trunc ratio [95% CI] |\n|---:|---:|---|---|---|---|---:|---:|---|\n'
for r in sorted(full,key=lambda r:(float(r['null_scale']),r['algorithm'],int(r['m']),r['mode'])):
    body+=f"| {r['null_scale']} | {r['m_minus_r']} | {r['algorithm']} | {r['mode']} | {r['gap_median']} [{r['gap_q25']}, {r['gap_q75']}] | {r['relative_gap_median']} [{r['relative_gap_q25']}, {r['relative_gap_q75']}] | {r['stable_count']}/32 | {r['finite_paired_count']}/32 | {r['dense_over_truncated_median']} [{r['paired95_low']}, {r['paired95_high']}] |\n"
body+='\nAn infinite upper IQR is preserved, not clipped to the successful outputs. Ratios use only finite paired endpoints and their counts are shown; they do not replace the failure-inclusive medians. No new run or parameter change. Original report tables/figures are preserved; the new REPORT.json pins their hashes.\n'
(ROOT/'X1/actor_full_table_reply.md').write_bytes(body.encode());append('X1','REPORT',body)
print(json.dumps(dict(status='COMPLETE',endpoint_rows=36,trajectories=1152,failed_PI=193,new_runs=0)))
