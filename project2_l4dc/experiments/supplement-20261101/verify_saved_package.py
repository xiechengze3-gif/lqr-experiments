"""Read-only integrity and CSV accounting checks; no solvers, sampling or policy evaluation."""
import argparse,csv,hashlib,json,math,tarfile,time
from collections import defaultdict
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
parser.add_argument('--output',type=Path)
parser.add_argument('--require-x3',action='store_true')
args=parser.parse_args();root=args.root.resolve()
out=args.output or root/'verification'/('saved-check-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'.json')
assert not out.exists(),'Choose a fresh receipt; previous checks are preserved'
def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):value.update(block)
    return value.hexdigest()
def read(path):
    with Path(path).open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def truth(value):return str(value).lower()=='true'
def q(values,p):
    v=sorted(values);at=p*(len(v)-1);lo,hi=math.floor(at),math.ceil(at)
    return v[lo] if lo==hi or v[lo]==v[hi] else math.inf if math.isinf(v[hi]) else v[lo]+(at-lo)*(v[hi]-v[lo])
def close(x,y):
    assert x==y or (math.isfinite(x) and math.isfinite(y) and abs(x-y)<=1e-10*max(1.,abs(x),abs(y))),(x,y)

old=json.loads((root/'provenance/old_files_sha256.json').read_text(encoding='utf-8-sig'))
for path,digest in old.items():assert sha(path)==digest,('Old file changed',path)
print(json.dumps(dict(old_files_unchanged=len(old))),flush=True)

x0=json.loads((root/'X0/verified_files.json').read_text())
assert len(x0['files'])==x0['count']==128
for row in x0['files']:
    target=root/'X0/data'/row['archive_path']
    assert target.stat().st_size==row['size'] and sha(target)==row['sha256']
early=json.loads((root/'X1/ce-delivery-manifest.json').read_text())
assert sha(root/'X1/ce-delivery-v1.tar.gz')==early['archive_sha256']
assert len(early['files'])==early['count']==1196
for row in early['files']:
    target=root/row['relative'];assert target.stat().st_size==row['size'] and sha(target)==row['sha256']

packages=[]
for path in sorted((root/'packages').glob('*.manifest.json')):
    d=json.loads(path.read_text());archive=root/'packages'/(d['name']+'.tar.gz')
    assert sha(archive)==d['archive_sha256']
    with tarfile.open(archive) as contents:
        for name,digest in d['source_hashes'].items():
            assert hashlib.sha256(contents.extractfile(name).read()).hexdigest()==digest
    packages.append(dict(name=d['name'],archive_sha256=d['archive_sha256']))
print(json.dumps(dict(X0_files=128,X1_CE_early_delivery_files=1196,frozen_auxiliary_packages=len(packages))),flush=True)

delivered={};archives=[];bytes_total=0
for path in sorted((root/'deliveries').glob('*.json')):
    d=json.loads(path.read_text(encoding='utf-8-sig'))
    if not {'archive_sha256','files','count'}.issubset(d):continue
    archive=path.with_suffix('.tar.gz');assert sha(archive)==d['archive_sha256'],str(archive)
    assert d['count']==len(d['files'])
    size=0
    for row in d['files']:
        target=(root/row['relative']).resolve();assert target.is_relative_to(root)
        assert target.stat().st_size==row['size'];size+=row['size']
        if target in delivered:assert delivered[target]==row['sha256']
        else:assert sha(target)==row['sha256'],str(target);delivered[target]=row['sha256'];bytes_total+=row['size']
    assert size==d['bytes'];archives.append(dict(manifest=path.name,files=d['count'],archive_sha256=d['archive_sha256']))
print(json.dumps(dict(verified_delivery_archives=len(archives),unique_verified_files=len(delivered))),flush=True)

actor_checks=[];pending=[]
for exp,scope,expected in [('X1','ACTOR',1152),('X2','NPG',128),('X3','NPG',1440)]:
    marker=root/exp/'report-actors/REPORT.json'
    if not marker.exists():pending.append(exp+' actor REPORT unavailable');continue
    proof=json.loads((root/exp/f'FORMAL_{scope}_COMPLETE.json').read_text())
    report=json.loads(marker.read_text());assert proof['status']==report['status']=='COMPLETE'
    assert proof['planned_actor_trajectories']==report['endpoints']==expected
    endpoints=read(marker.parent/'all_endpoints.csv');stats=read(marker.parent/'endpoint_statistics.csv')
    assert len(endpoints)==expected
    grouping=lambda r:(r['algorithm'],int(r['n']),int(r['m']),float(r.get('null_scale',0)),r.get('spectrum','exact'),int(r.get('budget_multiplier',1)),r['mode'])
    groups=defaultdict(list)
    for row in endpoints:
        groups[grouping(row)].append(row)
        if not truth(row['hard_failure']):assert int(row['actual_transitions'])==int(row['planned_transitions'])
    for cell in stats:
        rows=groups[grouping(cell)];assert len(rows)==32 and len({(r['system'],r['trial']) for r in rows})==32
        assert int(cell['stable_count'])==sum(truth(r['stable']) for r in rows)
        assert int(cell['failures'])==sum(not truth(r['stable']) for r in rows)
        values=[float(r[cell['metric']]) if truth(r['stable']) else math.inf for r in rows]
        for field,part in [('median',.5),('q25',.25),('q75',.75)]:close(float(cell[field]),q(values,part))
    pairs=read(marker.parent/'paired_ratios.csv');effects=read(marker.parent/'paired_bootstrap_effects.csv')
    lookup={grouping(r)+(r['system'],r['trial']):r for r in endpoints};pairgroups=defaultdict(list)
    for pair in pairs:
        key=grouping(pair);dense=lookup[key[:-1]+('dense',pair['system'],pair['trial'])]
        method=lookup[key+(pair['system'],pair['trial'])]
        finite=truth(dense['stable']) and truth(method['stable']) and float(method['gap'])>0
        assert finite==truth(pair['finite_pair'])
        if finite:close(float(pair['dense_over_method']),float(dense['gap'])/float(method['gap']))
        pairgroups[key].append(pair)
    for effect in effects:
        rows=pairgroups[grouping(effect)];assert len(rows)==32
        values=[float(r['dense_over_method']) for r in rows if truth(r['finite_pair'])]
        assert int(effect['finite_pairs'])==len(values) and int(effect['full_denominator'])==32
        if values:close(float(effect['paired_ratio_median']),q(values,.5))
    for item in proof['items']:
        rel=item['candidate_archive'].split('/results/supplement-20261101/',1)[1]
        assert sha(root/rel)==item['candidate_archive_sha256']
        if item.get('json_sha256'):
            rel=item['path'].split('/results/supplement-20261101/',1)[1]
            assert sha(root/rel)==item['json_sha256']
    actor_checks.append(dict(experiment=exp,endpoints=len(endpoints),summary_cells=len(stats),paired_rows=len(pairs),
       failed_endpoints=sum(not truth(r['stable']) for r in endpoints),hard_failures=proof['hard_failure_attempts'],
       independent_compute_policy_checks=report['candidate_policies_independently_checked'],
       local_check='Saved CSV statistics/ratios/counts/hashes only; no policy evaluations'))
    print(json.dumps(actor_checks[-1]),flush=True)

ce_checks=[]
for exp in ['X1','X2','X3']:
    marker=root/exp/'report-ce/REPORT.json';report=json.loads(marker.read_text())
    assert report['status']=='COMPLETE'
    rows=read(marker.parent/'all_records.csv');assert len(rows)==report['outputs']
    failures=sum(not truth(r['stable']) for r in rows)
    assert failures==report.get('failed_outputs',report.get('unstable_outputs'))
    fixed0=sum(not truth(r['stable']) and r['mode']=='k0' for r in rows)
    ce_checks.append(dict(experiment=exp,outputs=len(rows),failed_outputs=failures,fixed_k0_diagnostic_failures=fixed0,
        learning_failures=failures-fixed0))

extras=['analysis-P1-P2-v1/REPORT.json','X4/report/REPORT.json','X3/report-ce-rank-explanation-v4/REPORT.json',
        'X3/report-ce-failure-detail-v5/REPORT.json']
if (root/'X3/report-actors/REPORT.json').exists():
    extras+=['X3/report-actors-order-envelope-v2/REPORT.json','X3/report-npg-last-estimator-v1/REPORT.json',
             'X3/report-npg-failure-detail-v3/REPORT.json']
for name in extras:assert json.loads((root/name).read_text())['status']=='COMPLETE',name
ledger=json.loads((root/'budget/ledger.json').read_text(encoding='utf-8-sig'))
assert ledger['cap_SU']==200 and ledger['spent_SU']<=200
assert sum(j['requested_bound_SU'] for j in ledger['jobs'])<=200+1e-10
assert not args.require_x3 or not pending,pending
result=dict(status='PASS_COMPLETE' if not pending else 'PASS_AVAILABLE_WITH_PENDING_X3',checked_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
 old_files_unchanged=len(old),X0_verified_files=128,X1_CE_early_delivery_verified_files=1196,frozen_auxiliary_packages=packages,
 verified_delivery_archives=archives,unique_verified_delivery_files=len(delivered),
 unique_verified_delivery_bytes=bytes_total,actor_checks=actor_checks,ce_checks=ce_checks,pending=pending,
 ledger_snapshot_spent_SU=ledger['spent_SU'],ledger_snapshot_requested_bound_SU=ledger['requested_total_bound_SU'],
 ledger_snapshot_utc=ledger.get('last_accounting_utc'),new_policy_evaluations=0,new_learning_runs=0,new_training_transitions=0,
 script_sha256=sha(__file__),limits='Local check verifies saved data integrity and CSV arithmetic. Independent objective checks were separately performed on Slurm; bootstrap CIs are source-hashed, not independently re-estimated here.')
out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes((json.dumps(result,indent=2)+'\n').encode())
print(json.dumps(dict(status=result['status'],receipt=str(out),old_files_unchanged=len(old),pending=pending)),flush=True)
