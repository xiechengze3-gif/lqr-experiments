"""Append completed X6b REPORT only after full local delivery verification."""
import csv
import datetime
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'X6b-report-v1'
CHANNEL=ROOT.parents[2]
REVIEW='d5747708372e246b7bfd394c9c33ed915f4c7a20e6370aa1718032ba6b605e2e'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def fmt(value):
    if not value:return 'NA'
    v=float(value)
    return 'inf' if math.isinf(v) else f'{v:.6g}'
def interval(row,prefix):
    return f"{fmt(row[prefix+'_median'])}[{fmt(row[prefix+'_q25'])},{fmt(row[prefix+'_q75'])}]"
def ratio(row):
    return f"{fmt(row['paired_ratio_median'])}[{fmt(row['ci_low'])},{fmt(row['ci_high'])}]"

def main():
    task=CHANNEL/'CLAUDE_TASK.md'
    assert sha(task)==REVIEW
    manifest_path=OUT/'DELIVERY_MANIFEST.json'
    manifest=json.loads(manifest_path.read_text())
    assert manifest['status']=='COMPLETE_LOCAL_DELIVERY_VERIFIED'
    for name,digest in manifest['files'].items():assert sha(OUT/name)==digest
    with (OUT/'summary.csv').open(newline='') as stream:rows=list(csv.DictReader(stream))
    with (OUT/'attainment.csv').open(newline='') as stream:attainment=list(csv.DictReader(stream))
    header='## X6b REPORT — COMPLETE'
    reply=CHANNEL/'CODEX_REPLY.md'
    assert header not in reply.read_text(encoding='utf-8-sig')
    lines=[]
    labels={1/64:'1/64',1/16:'1/16',1/4:'1/4',1.:'1'}
    for row in rows:
        if row['ratio_kind']!='both_stable':continue
        full=next(r for r in rows if all(r[k]==row[k] for k in ['n','algorithm','rung']) and r['ratio_kind']=='failure_inclusive')
        values=[row['n'],row['algorithm'],labels[float(row['rung'])],row['primitive_per_arm'],
                row['dense_stable']+'/'+row['truncated_stable'],
                interval(row,'dense_relative_gap'),interval(row,'truncated_relative_gap'),
                ratio(row),ratio(full),row['bootstrap_invalid']]
        lines.append('|'+'|'.join(values)+'|')
    epsilon=[]
    for n in [24,36,48,72]:
        for alg in ['NPG','PI']:
            selected=[r for r in attainment if r['n']==str(n) and r['algorithm']==alg and r['arm']=='truncated']
            a=next(r for r in selected if r['relative_epsilon']=='0.1')
            b=next(r for r in selected if r['relative_epsilon']=='0.05')
            ca=json.loads(a['successes_by_rung'])[-1];cb=json.loads(b['successes_by_rung'])[-1]
            epsilon.append(f"|{n}|{alg}|{ca}/32|{a['status']}|{cb}/32|{b['status']}|")
    budget=manifest['accounting']
    body=f"""

{header}

All required frozen REPORT work and E-drive delivery are complete.
Review reread {datetime.datetime.now(datetime.timezone.utc).isoformat()},unchanged
SHA {REVIEW}; conditional00:30 authorization was used after full FORMAL coverage.
No extra experiments,retuning,retries,cancellations or paper TeX changes.

**Main finding:** NPG now shows clear terminal benefit. At the full rung,
paired dense/truncated gap median ratios are3.97519/5.67222/7.89184/11.3244 for
n24/36/48/72; PI ratios21.6135/29.9060/44.3077/65.9823. All full-rung arms32/32stable.
NPG all512 dense and512 truncated paths across all rungs are stable.
All198 dense failures are PI at1/64 or1/16; truncated fails0/1024.

Shallow delivery:experiments/x6-20261101/X6b-report-v1/README.md,
SCIENCE_REPORT.md,all10 original summary CSVs,tables/,figures-v4/,
SOURCE_HASHES.json,FIGURE_QA_v4.json,FINAL_ACCOUNTING_v1.json and DELIVERY_MANIFEST.json.
Manifest SHA256 {sha(manifest_path)}. Full local raw/provenance data and scripts
are in experiments/x6-20261101/X6b-protocol-v2/. Accepted original scientific
analysis SHAec275552... and config SHA6c0c6361... are byte-identical.

### Required per-rung table

M counts primitive transitions per arm/algorithm,including burn/baseline and
absorbing-failure padding. D/T=stable counts out of32; failure rate=(32-stable)/32.
Gap columns are FULL32 failure-inclusive relative gap median[Q25,Q75].
Ratios are per-pair g(dense)/g(truncated) then median[pointwise95%system-clusterCI],
not ratios of medians. BS5000 common draws resample8 systems with all4 seeds.
Both-stable(conditional) and failure-inclusive are both shown; empty conditional
resamples are counted. NA is not a dropped experiment. Absolute gap/IQR is fully
reported in tables/per-rung-gaps.md and summary.csv.

|n|algorithm|rung|M|D/T stable|dense relative gap|truncated relative gap|both-stable ratio[CI]|failure-inclusive ratio[CI]|empty conditional BS/5000|
|---|---|---|---:|---|---|---|---|---|---:|
{chr(10).join(lines)}

PI dense stable counts by rung are0/13/32/32(n24),0/5/32/32(n36),
0/30/32/32(n48),0/10/32/32(n72). Lowest-rung conditional ratios have no eligible
pairs; failure-inclusive ratios areinf. The audited total is exactly198
failures (128 at1/64,70 at1/16),all PI dense.
Full per-system,per-seed and both-failed counts remain in the CSVs.

### Observed epsilon ladder

All attained observed minima below occur only at the full rung. Dense NPG/PI
have0/32 successes at every rung for both epsilons and are right-censored.
The criterion is empirical>=29/32,not a95%-confidence population guarantee.

|n|algorithm|truncated success .1 at full|.1 status|truncated success .05 at full|.05 status|
|---|---|---:|---|---:|---|
{chr(10).join(epsilon)}

n24 truncated NPG/.1:30/32 observed successes,but1366/5000 bootstrap draws
are censored; budget CI=[189475712,inf]. Preserve this qualification.
Truncated NPG/.05 remains right-censored in all n. Truncated PI reaches both
registered epsilon criteria; quarter-rung medians below.1 do NOT meet29/32.
Dense minima are unobserved,so no exact dense/truncated budget factor is identified.
All32 attainment cells,CIs and censored mass are in attainment.csv and
tables/observed-epsilon.md; conditional epsilon ratios retain unidentified mass.

### Mechanism,implementation and theorem

Actual update/K-continuity recomputation errors are0 for both algorithms.
With this pre-calibrated practical schedule and population-selected T16/8,the
previous blanket statement 'NPG has no benefit' no longer describes X6b.
Evidence supports finite-budget precision/scheduling as important; this is not
a single-variable causal ablation of old experiments or proof of no common bug.

Low-N noisy-subspace attenuation persists: last-update NPG applied projection
medians n24/n72 are.200673/.0891361 at1/64 and.892922/.892985 at full; true rank2
tail is0. This is finite-sample suppression,not a nonzero discarded true tail.
rho_op at K0 or relative to Z is not an all-stage theorem/cancellation-error
certificate. See saved own-preupdate-target diagnostics,with padding NA and
learner-applied variants explicitly distinguished. Full-rung dense gap is
mostly null-action D; per-run gap decomposition and cost identities pass.

The learning equations match the paper; the empirically accepted H16/geometric
schedule does not numerically certify every worst-case appendix constant,
horizon,log factor and error event. Low-rung PI failures therefore alone do not
contradict the conditional every-iterate stability theorem. Recommend stable
1/4/full rungs for the main terminal-comparison panel,with the full ladder and
failures retained. Report NPG observed.1 attainment,unattained.05 and n24 infinite
upper CI explicitly. Old critic/LSTD variants should not be mixed into main
theorem validation. These are presentation recommendations; no paper was edited.

### Verification and resources

FORMAL384/384 allocations and REPORT5/5 allocations are COMPLETED.
Formal training transitions483160776704; REPORT zero new transitions.
Coverage1024 pairs/2048 arms,24576 raw stage NPZ and12288 checkpoint pairs.
All36864 matrix/checkpoint hashes,source/config/model hashes and exact primitive
budgets passed. Formal archive51,592files SHA
ef73e5871033bae2a1065ae047ad7e49bde5b9f6eed72738765c61df94c7a5e2;
report534files SHA
1b0242a7949f9801ca314b53aacbf482f664ad634841b18a935d552bbdbe09b6.
Both streamed archives and EVERY member were verified before E-drive extraction.
Max per-run gap-decomposition error6.408613988e-16; direct cost-identity error
9.499896335e-13. Final three PNG/SVG pairs were visually reviewed; v4 only fixes
labels/censor notation/legend placement. Original plot and intermediate versions
are preserved. Final figures use saved CSVs,not local policy/model computation.

X6 cumulative requested{budget['cumulative_requested_SU']:.9f}/400SU;
all-completed Slurm billed elapsed{budget['slurm_elapsed_billing_SU']:.9f}SU;
AMS settled{budget['ams_settled_walltime_slots_SU']:.9f}SU at{budget['checked_utc']}.
These overlap,never add. Final accounting is a separate post-completion file;
sealed logs/accounting inside archives are earlier snapshots. Old X0-X4 study
is separate. Main PuTTY/SSH/VPN unchanged. X6c stillDEFERRED; optional throttle
proposal was unused/moot. Keeping foreground review monitoring active for Claude.

STATUS: REPORT DONE X6b
"""
    assert sha(task)==REVIEW
    with reply.open('a',encoding='utf-8',newline='') as stream:stream.write(body)
    print(json.dumps(dict(status='REPORT_DONE_APPENDED',manifest_sha256=sha(manifest_path),per_rung_rows=len(lines))))

if __name__=='__main__':main()
