"""Append verified X3 formal/report channel replies from complete saved evidence."""
import argparse,csv,json,math
from collections import defaultdict
from control import ROOT,append,sha

p=argparse.ArgumentParser();p.add_argument('stage',choices=['FORMAL','REPORT']);a=p.parse_args()
cfgpath=ROOT/'configs/X3_NPG_formal_v1.json';cfg=json.loads(cfgpath.read_text())
proofpath=ROOT/'X3/FORMAL_NPG_COMPLETE.json';done=json.loads(proofpath.read_text())
assert done['status']=='COMPLETE' and done['bundles']==32 and done['planned_actor_trajectories']==1440
assert done['config_sha256']==sha(cfgpath)
def write(path,data):
    assert not path.exists(),'Existing deliverable is immutable'
    path.write_bytes(data.encode())
def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))
def formatted(r,base=''):
    return f"{float(r[base+'median']):.6g} [{float(r[base+'q25']):.6g}, {float(r[base+'q75']):.6g}]"

if a.stage=='FORMAL':
    body=f'''Scope: **X3 NPG FORMAL complete**, array20359471; all32 bundle receipts and288 multi-arm attempts are present, covering1,440 planned trajectories (8 systems x4 trials x3 spectra x3 budgets x5 ranks).

The accepted base8192, eta=.014930779908372525, T64, H32,16 pulse burn blocks and baseline, all RNG streams, ranks1/2/4/6/12 and batch multipliers1/4/16 were unchanged. Dense-only calibration and the largest-budget resource measurement preceded this array; no learning replay, post-hoc retuning or new experiment was submitted.

Coverage/source/count verification: hard-failure attempts {done['hard_failure_attempts']}; unequal actual-transition attempts {done['unequal_actual_transition_attempts']}; recorded outputs {done['recorded_outputs']}, failed recorded outputs {done['failed_recorded_outputs']}; independently assessed saved candidates {done['assessed_candidates']}. Failed endpoints by method: `{json.dumps(done['failed_endpoints'],sort_keys=True)}`. Every non-hard-failed arm consumed its exact planned transitions; absorbing-failure padding is separate and never called recovery. Planned transitions per arm are88,850,304 /355,296,768 /1,421,082,624 for the three batch multipliers (constant overhead means actual counts are not exactly1:4:16).

Proof `X3/FORMAL_NPG_COMPLETE.json`, SHA256 `{sha(proofpath)}`; config SHA256 `{sha(cfgpath)}`; engine SHA256 `{done['engine_sha256']}`. Local proof was copied byte-for-byte from Grace. Independent numerical policy checks and statistics remain REPORT work; this receipt does not claim numerical REPORT complete.

Next is the bounded15-minute REPORT package v28 (0.25 SU upper), including the Review04:35 saved last-estimator analysis. Its protocol is `X3_NPG_LAST_STAGE_ANALYSIS_v1.md`; no sampling rerun is needed. Unused prepared v26 is preserved and was never submitted.
'''
    write(ROOT/'X3/npg_formal_reply.md',body);append('X3','FORMAL',body,scope='NPG');print('X3 FORMAL appended');raise SystemExit(0)

interpretation=ROOT/'X3/npg_interpretation.md'
assert interpretation.exists(),'Write the final scientific interpretation after inspecting all tables/figures'
approval=json.loads((ROOT/'X3/ACCEPTED_REPORT_v28.json').read_text());assert approval['decision']=='ACCEPTED'
reportfolder=ROOT/'X3/report-actors';orderfolder=ROOT/'X3/report-actors-order-envelope-v2';errorfolder=ROOT/'X3/report-npg-last-estimator-v1'
reports=[json.loads((f/'REPORT.json').read_text()) for f in [reportfolder,orderfolder,errorfolder]]
assert all(r['status']=='COMPLETE' for r in reports)
assert reports[0]['engine_sha256']==reports[2]['engine_sha256']==done['engine_sha256']
assert reports[2]['config_sha256']==done['config_sha256']
for name in ['delivery-x3-npg-formal-raw-v1','delivery-x3-npg-final-reports-v1']:
    verified=json.loads((ROOT/'deliveries'/(name+'.verified.json')).read_text());assert verified['status']=='PASS'
stats=read(reportfolder/'endpoint_statistics.csv');effects=read(reportfolder/'paired_bootstrap_effects.csv')
envelope=read(orderfolder/'fixed_order_median_envelope.csv');last=read(errorfolder/'last_estimator_statistics.csv')
raw=read(reportfolder/'all_recorded_iterates.csv');endpoints=read(reportfolder/'all_endpoints.csv')
groups=defaultdict(list)
for r in raw:groups[(r['spectrum'],r['budget_multiplier'],r['mode'],r['system'],r['trial'])].append(r)
failpaths=[];perstage=defaultdict(list)
for key,rows in sorted(groups.items()):
    rows.sort(key=lambda r:int(r['stage']));bad=[r for r in rows if r['stable'].lower()!='true']
    failpaths.append(dict(spectrum=key[0],budget_multiplier=key[1],mode=key[2],system=key[3],trial=key[4],
        first_recorded_failed_stage=int(bad[0]['stage']) if bad else '',whole_path_stable=not bad and len(rows)==65,
        recorded_stages=len(rows),missing_planned_stages=65-len(rows)))
    for r in rows:perstage[key[:3]+(int(r['stage']),)].append(r)
detail=ROOT/'X3/report-npg-failure-detail-v3';assert not detail.exists();detail.mkdir()
def csvwrite(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
csvwrite(detail/'first_failure_paths.csv',failpaths)
counts=[]
planned_stage_keys=[(sp,str(mult),mode,stage) for sp in ['smooth','gapped','flat'] for mult in [1,4,16]
                    for mode in ['dense','k1','k2','k4','k6'] for stage in range(65)]
for key in sorted(planned_stage_keys):
    rows=perstage[key]
    counts.append(dict(spectrum=key[0],budget_multiplier=key[1],mode=key[2],stage=key[3],
      recorded_outputs=len(rows),full_denominator=32,stable_count=sum(r['stable'].lower()=='true' for r in rows),
      recorded_failed_count=sum(r['stable'].lower()!='true' for r in rows),missing_outputs=32-len(rows)))
csvwrite(detail/'per_update_failure_counts.csv',counts)
(detail/'REPORT.json').write_bytes((json.dumps(dict(status='COMPLETE',paths=len(failpaths),stage_cells=len(counts),
    source_sha256=sha(reportfolder/'all_recorded_iterates.csv'),source_code_sha256=sha(__file__),
    new_policy_evaluations=0,new_training_transitions=0),indent=2)+'\n').encode())

body=f'''Scope: **X3 NPG REPORT complete**, all planned1440 trajectories; independent numerical report job{reports[0]['job']}. No new sampled learning runs or transitions.

The source coverage proof verifies32 bundles/288 multi-runs. Numerical evaluation independently checked {reports[0]['candidate_policies_independently_checked']} saved candidate policies; max normalized direct-cost/gap identity discrepancy {reports[0]['max_normalized_gap_identity_error']:.6g}. Endpoint failures {reports[0]['failed_endpoints']}/1440; hard-failure attempts {reports[0]['hard_failure_attempts']}; unequal actual counts {reports[0]['unequal_actual_transition_attempts']}; discarded K0 padding transitions {reports[0]['padding_transitions']}. All failures remain+inf; no stable-subset replacement of medians.

All endpoint medians [q25,q75], each cell32 planned runs. M includes every burn/baseline/padding transition:

| Spectrum | batch mult | M | k | Stable/full | Absolute gap | Relative gap |
|---|---:|---:|---:|---|---|---|
'''
lookup={(r['spectrum'],r['budget_multiplier'],r['mode'],r['metric']):r for r in stats}
for r in sorted([r for r in stats if r['metric']=='gap'],key=lambda r:(r['spectrum'],int(r['budget_multiplier']),int(r['k']))):
    rel=lookup[(r['spectrum'],r['budget_multiplier'],r['mode'],'relative_gap')]
    body+=f"| {r['spectrum']} | {r['budget_multiplier']} | {int(r['planned_transitions']):,} | {r['k']} | {r['stable_count']}/32 | {formatted(r)} | {formatted(rel)} |\n"
body+='\nPaired dense/method gap ratios, finite/full pairs and system-cluster bootstrap95% (2,000 draws, seed2026110399). The same per-pair initial-gap normalization cancels, so relative-gap ratios coincide:\n\n| Spectrum | batch mult | k | Finite/full | Paired ratio | 95% CI |\n|---|---:|---:|---|---:|---|\n'
for r in sorted(effects,key=lambda r:(r['spectrum'],int(r['budget_multiplier']),int(r['mode'][1:]))):
    body+=f"| {r['spectrum']} | {r['budget_multiplier']} | {r['mode'][1:]} | {r['finite_pairs']}/32 | {float(r['paired_ratio_median']):.6g} | [{float(r['bootstrap95_low']):.6g}, {float(r['bootstrap95_high']):.6g}] |\n" if r['paired_ratio_median'] else f"| {r['spectrum']} | {r['budget_multiplier']} | {r['mode'][1:]} | 0/32 | undefined | undefined |\n"
body+='\nFixed-order group-median envelope (post-hoc diagnostic only, not online adaptive NPG):\n\n| Spectrum | batch mult | Best k by absolute-gap median | Stable/full | Envelope gap [IQR] |\n|---|---:|---:|---|---|\n'
for r in envelope:
    if r['metric']=='gap':body+=f"| {r['spectrum']} | {r['budget_multiplier']} | {r['best_k']} | {r['stable_count']}/32 | {float(r['envelope_median']):.6g} [{float(r['q25']):.6g}, {float(r['q75']):.6g}] |\n"
body+='\nReview04:35 mechanism: actual last update gives S_k=(K63-K64)/eta-RK63. The target is Z_K=-B^T P_K(A-BK) at that arm\'s actual K63. Raw Zhat of truncated arms was not saved and is not claimed recovered. The separate common-dense-policy/raw-estimate branch applies each rank offline to dense\'s recovered Zhat; it creates no alternative endpoint or training run. No top-2 redundant-cost identity is used for full-rank B.\n\nTwo-level last Frobenius errors, median [IQR]; own-arm versus common dense policy/estimate, available/full counts explicitly:\n\n| mult | k | Own-arm available | Own-arm ||S_k-Z_K||F | Common-dense available | Common-fit ||T_k(Zhat)-Z_K||F |\n|---:|---:|---|---|---|---|\n'
lastlook={(r['branch'],r['spectrum'],r['budget_multiplier'],r['k'],r['metric']):r for r in last}
for mult in ['1','4','16']:
    for k in ['1','2','4','6','12']:
        own=lastlook[('own_arm_actual_update','gapped',mult,k,'error_fro')]
        common=lastlook[('common_dense_policy_and_raw_estimate','gapped',mult,k,'error_fro')]
        body+=f"| {mult} | {k} | {own['valid_estimators']}/32 | {formatted(own) if own['median'] else 'undefined'} | {common['valid_estimators']}/32 | {formatted(common) if common['median'] else 'undefined'} |\n"
body+=f'''
Saved-gain mechanism checks: {reports[2]['own_arm_available_final_updates']}/1440 actual final updates available; max recovered rank residual {reports[2]['max_recovered_rank_residual']:.6g}; update reconstruction residual {reports[2]['max_update_reconstruction_residual']:.6g}; synthetic recovery error {reports[2]['synthetic_recovery_max_error']:.6g}. All spectra/normalized errors/true current-target rank-k tails and error-ratio bootstrap are in the accompanying CSV. Frobenius errors include finite-H bias, sampling and truncation effects; they do not alone certify a theorem small-error constant.

Files: `X3/report-actors/endpoint_statistics.csv`, `all_endpoints.csv`, `all_recorded_iterates.csv`, `paired_bootstrap_effects.csv`, `primitive_transition_counts.csv`, `system_certificates.csv`; `report-actors-order-envelope-v2/fixed_order_median_envelope.csv`, `true_B_spectral_tails.csv`, `fixed_order_iqr_gap.png/.svg`, `fixed_order_iqr_relative_gap.png/.svg`, `best_fixed_order.png/.svg`; `report-npg-last-estimator-v1/last_stage_per_output.csv`, `last_estimator_statistics.csv`, `paired_last_error_bootstrap.csv`, `recovered_effective_estimates_and_targets.npz`, two `last_error_*.png/.svg`, `two_level_endpoint_gaps.png/.svg`. Corresponding CSV are the figure numerical sources. First-failure and each-update counts are in new `report-npg-failure-detail-v3/`.

Full raw288 JSON+288 candidate NPZ and32 bundle receipts, proof and reports were delivered with archive/per-file hashes; local source files were never overwritten with differing bytes. Figures were visually inspected before this REPORT append. Formal config SHA256 `{sha(cfgpath)}`; report package/source/config hashes in `packages/supplement-20261101-x3-actor-report-v28.manifest.json`; exact data-source hashes in all three `REPORT.json` files.

NPG conclusions are fixed-budget empirical comparisons only. No epsilon attainment, success-probability theorem, fitted dimension law or monotone-order law is claimed. True-B tau/beta tables are B-spectrum diagnostics, not every current Z_K tail; the last-stage mechanism tables separately evaluate the actual current Z_K. No adaptive NPG was run. All practical/theorem-regime limitations and negative cells are retained. Optional n48 remains deferred as accepted; no additional experiment was added.
'''
body+='\n'+interpretation.read_text()+'\n'
write(ROOT/'X3/npg_report_reply.md',body);append('X3','REPORT',body,scope='NPG')
print(json.dumps(dict(status='REPORT_APPENDED',failure_detail_paths=len(failpaths),failure_stage_cells=len(counts))))
