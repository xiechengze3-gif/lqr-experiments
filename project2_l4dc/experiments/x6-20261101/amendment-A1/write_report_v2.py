"""Saved CSV/scalar-only X6a report. No scientific matrix evaluation."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPORT=ROOT/'deliveries/report-20365069-v4/X6a/reports/v1'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(name):
    with (REPORT/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def f(value):return f'{float(value):.4g}'
def interval(row,key):return f(row[key+'_median'])+' ['+f(row[key+'_q25'])+', '+f(row[key+'_q75'])+']'


def main():
    rows=read('summary.csv');cal=read('calibration.csv')
    selected=[];table=[]
    for family in ['S','U']:
        for n in [24,36,48,72]:
            for algorithm in ['NPG','PI','CE']:
                N=524288 if algorithm=='CE' or n<48 else 4194304
                pair={r['arm']:r for r in rows if r['role']=='formal' and r['family']==family
                      and r['n']==str(n) and r['algorithm']==algorithm and r['N']==str(N)}
                d,t=pair['dense'],pair['truncated']
                assert d['finite_observations']==d['full_observations']=='32'
                selected.append(dict(family=family,n=n,algorithm=algorithm,N=N,
                    dense_error_median=d['relative_error_median'],dense_q25=d['relative_error_q25'],dense_q75=d['relative_error_q75'],
                    truncated_error_median=t['relative_error_median'],truncated_q25=t['relative_error_q25'],truncated_q75=t['relative_error_q75'],
                    paired_error_ratio_median=d['paired_error_ratio_median'],
                    paired_error_ratio_q25=d['paired_error_ratio_q25'],paired_error_ratio_q75=d['paired_error_ratio_q75'],
                    dense_rho_op=d['rho_op_median'],left_sin_theta=d['left_sin_theta_median'],
                    dense_projection_mean=d['projection_mean'],dense_projection_se=d['projection_se'],
                    truncated_projection_mean=t['projection_mean'],truncated_projection_se=t['projection_se'],finite=32,full=32))
                table.append('| '+' | '.join([family,str(n),algorithm,str(N),
                    interval(d,'relative_error'),interval(t,'relative_error'),
                    interval(d,'paired_error_ratio'),f(d['rho_op_median']),
                    f(d['left_sin_theta_median']),'32/32'])+' |')
    target=ROOT/'report-v2';assert not target.exists();target.mkdir()
    with (target/'largest_budget_comparison.csv').open('x',encoding='utf-8',newline='') as out:
        w=csv.DictWriter(out,fieldnames=list(selected[0]));w.writeheader();w.writerows(selected)
    calibration=[]
    for family in ['S','U']:
        for n in [24,36,48,72]:
            values={r['algorithm']:(r['smallest_N'] or '>'+r['censored_above_N'])
                    for r in cal if r['family']==family and r['n']==str(n)}
            calibration.append('| '+' | '.join([family,str(n),values['NPG'],values['PI_raw'],values['PI']])+' |')
    figures=json.loads((ROOT/'figures-v3/manifest.json').read_text())
    assert figures['csv_sha256']==sha(REPORT/'summary.csv') and len(figures['files'])==24
    for item in figures['files']:assert sha(ROOT/'figures-v3'/item['path'])==item['sha256']
    verification=json.loads((REPORT/'verification.json').read_text())
    account_paths=sorted((ROOT/'deliveries/report-20365069-v4/budget').glob('accounting-*.json'))
    account=json.loads(account_paths[-1].read_text())
    text='''# X6a REPORT v1 — estimation gains and the low-signal failure mechanism

All40 formal/calibration bundles and all320 fixed-gain paths are complete.
12800 observation rows,1920 Stein prefixes,1600 CE fits and3520 estimate-file
hashes passed the accepted Slurm REPORT. All formal cells have32/32 finite
fits. This is **fixed-gain estimation**, not a closed-loop performance experiment.

The new result supports the original diagnosis: rank2 compression lowers
Frobenius error, but when raw signal/noise is poor it can discard much of the
true signal. On S/n24/N2048, raw Z projection is0.9708+/-0.1256 versus
truncated0.1794+/-0.05855; sin(theta)=0.9961. At N524288, projection recovers
to1.0032+/-0.01007 versus0.9844+/-0.01279 and sin(theta)=0.3726.
These are means +/- system SE; errors/angles below use seed-then-system medians.

On S at their largest registered N, NPG paired error ratios are2.34/2.64/3.47/4.00
for n24/36/48/72; PI joint-compression ratios2.44/3.02/3.57/4.32. CE B-estimation
ratios at N524288 are2.46/3.04/3.57/4.26. Ratios are within-system/seed before
hierarchical aggregation; they are not ratios of marginal medians or cost gains.
Do not compare Stein block N with CE transition N as equal sample cost.

The unfiltered U family remains noisy even at the largest budgets: formal NPG
rho_op medians3.75/4.05/5.72/5.90, sin(theta)0.978/0.996/0.996/0.998, and
truncated projections0.453/0.252/0.211/0.161. Its smaller Frobenius errors alone
do not establish a good update direction. PSD-clipped PI and raw-PI are kept
separately; clipping can itself change signal projection. No variant is retuned.

## Largest registered budgets, all formal systems

Each bracket is IQR over8 system medians, after seed medians within each system.
PI uses [G+,Zhat] versus the exact actor_learner two-sided compressed pair.
All other budgets and raw-PI diagnostics remain in the source CSVs.

| Family | n | Estimator | N | Dense relative error [IQR] | Truncated [IQR] | Paired ratio [IQR] | Dense rho_op | Left sin(theta) | Finite/full |
|---|---:|---|---:|---|---|---|---:|---:|---|
'''+ '\n'.join(table)+'''

## Pilot-only calibration, dense estimate only

The criterion is median over2 pilot-system seed medians of rho_op<=1.
It is an empirical precision threshold, not all theorem hypotheses. Separate
raw/clipped PI thresholds are not silently used as the common NPG actor base.

| Family | n | NPG smallest N | Raw PI smallest N | Clipped PI smallest N |
|---|---:|---:|---:|---:|
'''+ '\n'.join(calibration)+'''

**S/n36 NPG is right-censored above524288.** It has no valid calibrated base
in the frozen grid. Do not substitute its formal median, use the PI base, or
extrapolate a qualifying N. All U pilot calibration is right-censored as well.
X6b requires a reviewer-approved S/n36 pilot-grid extension; X6c additionally
needs the approved P0<=15 pilot-selection rule, which may select different U IDs.

## Reproduction and evidence

- CSVs: ../deliveries/report-20365069-v4/X6a/reports/v1/{observations,
  system_summaries,summary,calibration,certificates}.csv.
- Figures: ../figures-v3,12 plots/24PNG+SVG; manifest has source and CSV hashes.
  ../plot_saved_v3.py is CSV-only. v1/v2 are preserved; v3 only widens panels, fixes shared errorbar x limits, and
  uses rotated power-of-two ticks after visual inspection found overlapping labels.
  No numerical summary, filtering, or scientific method changed.
- All4897 formal-delivery files and64 report-delivery files were SHA-verified
  after transfer; resource delivery adds29 files. Separate snapshots preserve
  overlaps in logs/accounting instead of overwriting historical files.
- Source/config/code are in the immutable formal/report package manifests.
  Accepted analysis SHA0962905f641e9f75eb16f16c47fcfb160c73614234c23cc269db21c9ebaa0cda.
  Exact PI processing comparison maximum relative difference2.22092e-13.
- Resource20364669, formal20364803, report20365069; report84seconds,
  zero additional simulated transitions. Primitive count18287459840 for
  formal collection counts nested prefixes once and includes burn/baseline.

## Interpretation for manuscript and next experiment

These plots are suitable as a mechanism figure or appendix evidence. They show
why a lower total estimator error can coexist with severe signal attenuation
at practical low budgets. They do not alone prove a terminal-cost improvement,
epsilon attainment, universal NPG superiority or a theorem counterexample.
At exact rank2 there is no true discarded spectral tail in Z; nonlinear noisy
rank truncation is distinct from structural full-rank tail bias. The bitwise
check validates agreement with the frozen collector, not every theorem constant.
Keep the U negative result and S/n36 calibration censoring visible.

Next: propose X6b with S bases524288 / PENDING /2097152 /4194304, common eta0.2,
the registered population R2 rule for T, and rungs1/16,1/4,1. A small separate
pilot-only S/n36 extension and explicit approval are needed before resolving it.
No actor learning or X6c selection/calibration was started in this report.
'''
    text+=f"\nX6 requested upper {account['cumulative_requested_SU']:.9f}/400SU; Slurm elapsed {account['slurm_elapsed_billing_SU']:.9f}SU; AMS settled {account['ams_settled_walltime_slots_SU']:.9f}SU (overlapping views; do not add).\n"
    (target/'README.md').write_text(text,encoding='utf-8',newline='\n')
    manifest=dict(status='REPORT_DELIVERY_COMPLETE',report_verification=verification,
        requested_SU=account['cumulative_requested_SU'],elapsed_SU=account['slurm_elapsed_billing_SU'],
        settled_SU=account['ams_settled_walltime_slots_SU'],
        figures_manifest_sha256=sha(ROOT/'figures-v3/manifest.json'),
        source_csv_sha256=sha(REPORT/'summary.csv'),
        files={p.name:sha(p) for p in target.iterdir() if p.is_file()})
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='report_verification'}))


if __name__=='__main__':main()
