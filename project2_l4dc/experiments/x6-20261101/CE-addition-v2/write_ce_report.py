"""Saved CSV/scalar-only report assembly; never evaluates a policy."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'deliveries/ce-20365253-v7/X6a/CE-addition-v1'


def read(name):
    with (DATA/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def fmt(value):
    if not value:return 'NA'
    number=float(value)
    return 'inf' if math.isinf(number) else f'{number:.5g}'
def ratio(row):return fmt(row['ratio_median'])+' ['+fmt(row['ci_low'])+', '+fmt(row['ci_high'])+']'
def gap(row,arm,kind):
    key=arm+'_'+kind
    return fmt(row[key+'_median'])+' ['+fmt(row[key+'_q25'])+', '+fmt(row[key+'_q75'])+']'


def main():
    proof=json.loads((ROOT/'VERIFIED.json').read_text())
    assert proof['status']=='PASS_TRANSFER_HASHES_COVERAGE_AND_SCALAR_ARITHMETIC'
    rows=read('summary.csv');cert=read('certificate_summary.csv')
    figures=json.loads((ROOT/'figures-v1/manifest.json').read_text())
    assert figures['csv_hashes']['summary.csv']==sha(DATA/'summary.csv')
    for item in figures['files']:assert sha(ROOT/'figures-v1'/item['path'])==item['sha256']
    groups={(r['family'],r['n'],r['N'],r['ratio_kind']):r for r in rows}
    ratio_table=[];gap_table=[]
    for family in ['S','U']:
        for n in [24,36,48,72]:
            for N in [2048,8192,32768,131072,524288]:
                b=groups[(family,str(n),str(N),'both_stable')]
                f=groups[(family,str(n),str(N),'failure_inclusive')]
                ratio_table.append('| '+' | '.join([family,str(n),str(N),ratio(b),ratio(f),
                    b['dense_stable']+'/32',b['truncated_stable']+'/32',b['ratio_pairs']+'/32',f['dropped_pairs']+'/32'])+' |')
                gap_table.append('| '+' | '.join([family,str(n),str(N),gap(b,'dense','gap'),
                    gap(b,'truncated','gap'),gap(b,'dense','relative_gap'),gap(b,'truncated','relative_gap')])+' |')
    cert_table=[]
    for r in cert:
        cert_table.append('| '+' | '.join([r['family'],r['n'],
            fmt(r['P0_op_median'])+' ['+fmt(r['P0_op_q25'])+', '+fmt(r['P0_op_q75'])+']',
            fmt(r['v_star_median'])+' ['+fmt(r['v_star_q25'])+', '+fmt(r['v_star_q75'])+']'])+' |')
    accounts=sorted((ROOT/'deliveries/ce-20365253-v7/budget').glob('accounting-*.json'))
    account=json.loads(accounts[-1].read_text())
    text='''# X6a saved-data CE REPORT

All1280 saved formal OLS fits were evaluated with dense and rank2 CE, using
the identical fit/prefix for each pair. No new simulated transition was used.
Dedicated Slurm20365253 completed164s;1280 gain archives and all1349 delivered
files were hash-verified after transfer. Exact direct-cost/quadratic-gap identity
check maximum normalized discrepancy6.96641e-11. All40 both-stable pointwise
95% system-bootstrap intervals lie above1; this is not a simultaneous interval.

**Fixed-certificate family S gives a clear dimension trend.** At N2048 the paired
gap ratios for n24/36/48/72 are5.899/8.146/10.390/15.685, with95% intervals
[5.301,6.634]/[7.388,9.082]/[9.785,11.081]/[14.897,16.195]. Both arms are
32/32 stable at every S budget. P0 medians stay between1.535 and1.552, under
the common1.5625 class bound. This is a common certificate class, not identical
P0 or identical plants across dimensions. Ratios are always paired on the same
plant/seed; no fitted dimension law is claimed.

U remains useful as a separate uncontrolled-conditioning check. At N2048,
n48 stable counts are19/32 dense and28/32 truncated; n72 counts18/32 and27/32.
Their both-stable ratios23.596 and26.247 differ from the failure-inclusive
31.898 and58.724, whose upper95% bounds are infinite. Jointly failed pairs
(4/32 and5/32) are explicitly reported and only those are dropped from the
failure-inclusive ratio. Full-denominator gap medians include all failures.
Do not infer a universal n-only law from the U family, whose certificate and
optimal sensitivity vary substantially.

## Paired gap ratios and full denominators

Brackets are95% percentile intervals from5000 system-cluster resamples of8
systems, retaining4 seeds per sampled system. Both definitions use preregistered
separate bootstrap streams, so their CI endpoints can differ slightly even when
all pairs are stable; point estimates then agree. Raw failures/reasons are kept.
Failure-inclusive ratio keeps dense-only failure asinf and truncated-only failure
as0; it drops only jointly failed pairs. A both-zero optimal-gap pair would
receive ratio1. No such convention changes the full32 gap medians.

| Family | n | N | Both-stable ratio [95% CI] | Failure-inclusive ratio [95% CI] | Dense stable | Trunc stable | Both-stable pairs | Joint failures dropped |
|---|---:|---:|---|---|---|---|---|---|
'''+ '\n'.join(ratio_table)+'''

## Full-denominator gaps, including unstable/failed outputs as infinity

Brackets are IQR over all32 paths. Relative gap divides by the same plant's
initial K0 gap. These medians are not conditioned on being both-stable.

| Family | n | N | Dense abs gap [IQR] | Trunc abs gap [IQR] | Dense rel gap [IQR] | Trunc rel gap [IQR] |
|---|---:|---:|---|---|---|---|
'''+ '\n'.join(gap_table)+'''

## Certificates,8 distinct systems per cell

| Family | n | P0 operator norm median [IQR] | v_star median [IQR] |
|---|---:|---|---|
'''+ '\n'.join(cert_table)+'''

## Reproduction and scope

- Source CSVs and gains: deliveries/ce-20365253-v7/X6a/CE-addition-v1/.
- Full source/config/approval: packages/x6-20261101-a-ce-report-v7.manifest.json.
  Source a10aef06ec2c7c08a9b027d2f57b53f6ec9e8405f81892e9315acf23960a99da;
  engine9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989.
- CSV-only plot_ce_saved.py; figures-v1 has3PNG/SVG pairs. Every ratio figure
  includes per-(n,N) stable counts out of32. Infinite upper bounds use arrows;
  the unbounded intervals remain exact in CSV. Figures visually checked.
- VERIFIED.json independently checks file hashes, coverage, stored-count and
  scalar median arithmetic locally; all policy/DARE/Lyapunov work ran on Slurm.
- Controller-only v2 fixes the single-field sacct State delimiter check before
  first submission. v6 was never submitted/reserved; no model/config change.
- These results support CE's within-system advantage and the dimension trend
  in a uniform stable certificate class. They do not establish NPG/PI terminal
  gains, literal satisfaction of every theorem constant, or any epsilon claim.
- Original X6a datasets, all prior reports/releases and paper TeX stay unchanged.
'''
    text+=f"\nX6 requested{account['cumulative_requested_SU']:.9f}/400SU, actual Slurm{account['slurm_elapsed_billing_SU']:.9f}SU, AMS settled{account['ams_settled_walltime_slots_SU']:.9f}SU; snapshot{account['checked_utc']}, overlapping views, do not add.\n"
    path=ROOT/'REPORT.md';assert not path.exists();path.write_text(text,encoding='utf-8',newline='\n')
    manifest=dict(status='REPORT_COMPLETE',report_sha256=sha(path),verification_sha256=sha(ROOT/'VERIFIED.json'),
        figures_manifest_sha256=sha(ROOT/'figures-v1/manifest.json'),source_csv_sha256=sha(DATA/'summary.csv'),
        requested_SU=account['cumulative_requested_SU'],elapsed_SU=account['slurm_elapsed_billing_SU'],
        settled_SU=account['ams_settled_walltime_slots_SU'],new_transitions=0)
    (ROOT/'REPORT_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest))


if __name__=='__main__':main()
