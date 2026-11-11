"""Independent numerical audit and publication report from completed outputs."""
import argparse
import hashlib
import json
import math
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.linalg import solve_discrete_lyapunov
from dense_scaling import evaluate,atomic_json
from direct_stein_final import correct
from final_npg_audit import write_csv
from final_round_report import load_csv


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(out):
    cfg=json.loads((out/'frozen_config.json').read_text());config_hash=sha(out/'frozen_config.json')
    for name,digest in cfg['sources'].items():
        assert sha(ROOT/name)==digest,('Current scientific source changed',name)
        assert sha(out/'frozen'/name)==digest,('Frozen scientific source changed',name)
    files=sorted((out/'core').glob('n*.json'))
    assert len(files)==cfg['planned_core_trajectories'],f'{len(files)}/72 core trajectories'
    expected={(s,d,b,m) for s in cfg['system_seeds'] for d in cfg['sampling_seeds']
              for b in cfg['blocks_per_update'] for m in cfg['methods']}
    seen=set();actual=0;failures=defaultdict(int);endpoints=[];conditions=defaultdict(float)
    for path in files:
        data=json.loads(path.read_text());meta=data['meta'];rows=data['rows']
        key=(meta['system_seed'],meta['sampling_seed'],meta['blocks'],meta['method'])
        assert key not in seen;seen.add(key)
        assert meta['config_sha256']==config_hash
        unit=cfg['burn']+(meta['blocks']+1)*cfg['horizon']
        for stage,row in enumerate(rows):
            assert row['stage']==stage and row['transitions']==unit*stage
            if row.get('normalized_gap') is not None:
                np.testing.assert_allclose(row['normalized_gap'],row['gap']/data['initial_gap'],rtol=1e-12)
            for residual in ('critic_relative_residual','update_relative_residual'):
                if residual in row:assert row[residual]<=cfg['solve_relative_residual_tolerance']
            for key in ('gram_condition','R_plus_G_condition','critic_relative_residual','update_relative_residual'):
                if key in row:conditions[key]=max(conditions[key],row[key])
        assert rows[-1]['transitions']==meta['actual_transitions']
        if meta['status']=='completed':assert rows[-1]['stage']==8 and rows[-1]['stable']
        else:assert rows[-1]['failure']==meta['status']
        actual+=meta['actual_transitions'];failures[meta['status']]+=1
        with np.load(out/'core/systems'/f"n50-r4-s{meta['system_seed']}.npz") as d:
            s={k:d[k].copy() for k in d.files}
        with np.load(path.with_suffix('.npz')) as d:k=d['K']
        # A numerical solve failure can leave K at the last executable policy.
        if meta['status']!='numerical_failure':
            q,_=evaluate(s,k);assert q['stable']==rows[-1]['stable']
            if q['stable']:np.testing.assert_allclose(q['gap'],rows[-1]['gap'],rtol=1e-9,atol=1e-8)
        endpoints.append(dict(meta,g=rows[-1]['normalized_gap'],gap=rows[-1]['gap']))
    assert seen==expected
    rank8_files=list((out/'rank8').glob('n*.json'))
    assert len(rank8_files)==6,'The predeclared two-system rank-8 confirmation is incomplete'
    rank8_keys=set()
    for path in rank8_files:
        data=json.loads(path.read_text());meta=data['meta'];rows=data['rows']
        rank8_keys.add((meta['system_seed'],meta['method']))
        assert meta['n']==50 and meta['r']==8 and meta['eta']==.25 and meta['blocks']==131072
        assert meta['sampling_seed']==0
        for row in rows:assert row['transitions']==row['stage']*(512+131073*16)
        assert meta['actual_transitions']==rows[-1]['transitions']
        if meta['status']=='completed':assert rows[-1]['stage']==8
    assert rank8_keys=={(s,m) for s in (1101,1102) for m in cfg['methods']}
    fullrank_checks=0
    for path in (out/'scaling').glob('n50-r50*.npz'):
        with np.load(path) as d:g,z=d['G'],d['Z']
        dense=correct(g,z,'dense');rank50=correct(g,z,'known_rank',known_rank=50)
        np.testing.assert_array_equal(dense[0],rank50[0]);np.testing.assert_array_equal(dense[1],rank50[1])
        fullrank_checks+=1
    assert fullrank_checks==4
    npg=json.loads((out/'npg-audit/summary.json').read_text())
    assert npg['archived_trajectories']==672 and npg['instabilities']==98
    assert npg['exact_critic_runs']==28 and npg['exact_critic_sampled_transitions']==0
    old=json.loads((out/'old-pi-audit/summary.json').read_text());assert len(old['replays'])==24 and old['replay']=='PASS'
    failure_test_log=(ROOT/'receipts/final-round-failure-tests-20261014.log').read_text(encoding='utf-8')
    assert 'Ran 2 tests' in failure_test_log and 'OK' in failure_test_log and 'FAILED' not in failure_test_log
    ledger=[]
    for name in ('core','debug','pilot-learning','rank8'):
        rows=[json.loads(p.read_text()) for p in (out/name).glob('n*.json')]
        ledger.append(dict(phase=name,runs=len(rows),transitions=sum(d['meta']['actual_transitions'] for d in rows)))
    for name in ('pilot-fixed','scaling'):
        rows=[json.loads(p.read_text()) for p in (out/name).glob('*.json')]
        ledger.append(dict(phase=name,runs=len(rows),transitions=sum(d['physical_transitions'] for d in rows)))
    # Old replay performs two counted 65536-block critics for each of 12 paths.
    ledger.append(dict(phase='old-pi-audit',runs=24,transitions=24*(1024+65537*16)))
    benchmark=json.loads((out/'resource_benchmark.json').read_text())
    ledger.append(dict(phase='initial-benchmark',runs=1,transitions=benchmark['transitions']))
    horizon=json.loads((out/'horizon-audit/summary.json').read_text())
    ledger.append(dict(phase='old-policy-horizon-audit',runs=4,transitions=horizon['actual_transitions']))
    residual_path=out/'old-residual-check/summary.json'
    deadline=time.monotonic()+300
    if not residual_path.exists():print('Waiting for the separately queued old-system diagnostic.',flush=True)
    while not residual_path.exists() and time.monotonic()<deadline:time.sleep(2)
    if not residual_path.exists():raise RuntimeError('Old-system diagnostic has not completed; core results remain preserved.')
    residual_check=json.loads(residual_path.read_text())
    assert len(residual_check['endpoints'])==12
    ledger.append(dict(phase='old-system-two-step-residual-check',runs=12,transitions=residual_check['actual_transitions']))
    write_csv(out/'report/transition_ledger.csv',ledger)
    receipt=ROOT/'receipts/final-round-core-20261014.json';wall_seconds=None
    if receipt.exists():
        start=datetime.fromisoformat(json.loads(receipt.read_text())['started_utc'].replace('Z','+00:00')).timestamp()
        wall_seconds=max(p.stat().st_mtime for p in files)-start
    result=dict(status='PASS',core_trajectories=len(files),rank8_trajectories=len(rank8_files),actual_core_transitions=actual,
        core_wall_seconds=wall_seconds,
        planned_core_transitions=cfg['planned_core_transitions'],core_outcomes=dict(failures),
        source_revision_sha256=cfg['source_revision_sha256'],fullrank_bitwise_checks=fullrank_checks,
        old_stage_replays=24,archived_npg_trajectories=672,new_sampled_npg_transitions=0,
        frozen_learner_unit_tests=9,supplementary_failure_path_tests=2,
        transition_ledger_scope='Sampled studies, pilots, replays and benchmark; analytic oracle steps and unit-test fixtures excluded.',
        maximum_numerical_diagnostics=dict(conditions),
        total_new_physical_transitions=sum(r['transitions'] for r in ledger))
    atomic_json(out/'report/final_audit.json',result)
    return cfg,result,endpoints


def publication_report(out,cfg,validation):
    report=out/'report';summary=json.loads((report/'summary.json').read_text())
    by_budget=defaultdict(dict)
    for r in summary['core']:by_budget[r['blocks']][r['method']]=r
    def fmt(x):return 'failure dominated' if x is None else f'{x:.4f}'
    table=['| Blocks per update | Total transitions | Dense median g and success | Known rank median g and success | Adaptive median g and success |',
           '| --- | --- | --- | --- | --- |']
    for b,methods in sorted(by_budget.items()):
        row=[str(b),f"{methods['dense']['planned_transitions']:,}"]
        row += [f"{fmt(methods[m]['median_g'])}; {methods[m]['success']}/{methods[m]['runs']}" for m in ('dense','known_rank','adaptive')]
        table.append('| '+' | '.join(row)+' |')
    initial=load_csv(out/'npg-audit/initial_diagnostics.csv');noise=load_csv(out/'npg-audit/initial_noise.csv')
    exact=load_csv(report/'npg_exact_target_iterations.csv');control=load_csv(out/'population-controls/population_controls.csv')
    diagnostics=[]
    for rank in (1,2,4,8,16,32,50):
        rows=[r for r in initial if int(r['rank'])==rank]
        errs=[float(r['noise_fro2']) for r in noise if int(r['rank'])==rank and r['method']=='raw' and int(r['blocks'])==32768]
        zs=[float(r['Z0_fro']) for r in rows]
        iterations=[int(r['first_iteration']) for r in exact if int(r['rank'])==rank]
        diagnostics.append(dict(rank=rank,initial_gap_mean=float(np.mean([float(r['initial_gap']) for r in rows])),
            rho_mean=float(np.mean([float(r['rho']) for r in rows])),B_fro_mean=float(np.mean([float(r['B_fro']) for r in rows])),
            Z_fro_mean=float(np.mean(zs)),raw_noise_fro2_mean=float(np.mean(errs)),
            raw_noise_to_Z_energy=float(np.mean(errs)/np.mean(np.square(zs))),
            exact_target_iterations_min=min(iterations),exact_target_iterations_max=max(iterations)))
    # Reachability diagnostic uses the saved reconstructed matrices, not an estimated model.
    reachability=[]
    for path in sorted((out/'npg-audit').glob('npg-system*.npz')):
        rank=int(path.stem.split('-r')[1].split('-')[0]);seed=int(path.stem.rsplit('-s',1)[1])
        with np.load(path) as d:
            f=d['A']-d['B']@d['K0'];term=d['B'].copy();gram=np.zeros_like(f)
            for _ in range(16):gram+=term@term.T;term=f@term
            p0=solve_discrete_lyapunov(f.T,d['Q']+d['K0'].T@d['R']@d['K0'])
            action_hessian=d['R']+d['B'].T@p0@d['B'];heig=np.linalg.eigvalsh(action_hessian)
        eig=np.maximum(np.linalg.eigvalsh((gram+gram.T)/2),0)
        reachability.append(dict(rank=rank,system_seed=seed,H=16,gram_trace=float(eig.sum()),
            numerical_rank=int(np.count_nonzero(eig>1e-10*eig[-1])),relative_rank_tolerance=1e-10,
            initial_action_curvature_min_eigenvalue=float(heig[0]),
            initial_action_curvature_max_eigenvalue=float(heig[-1]),
            interpretation='offline finite-horizon closed-loop reachability diagnostic'))
    for row in diagnostics:
        row['action_curvature_min_eigenvalue_mean']=float(np.mean([r['initial_action_curvature_min_eigenvalue'] for r in reachability if r['rank']==row['rank']]))
    write_csv(report/'npg_control_difficulty.csv',diagnostics);write_csv(report/'npg_reachability.csv',reachability)
    ratios=json.loads((out/'npg-audit/summary.json').read_text())['budget_ratios']
    archived_endpoints=load_csv(out/'npg-audit/endpoints.csv');stability=defaultdict(list)
    for row in archived_endpoints:
        stability[(int(row['rank']),row['method'],row['schedule'].split('-final-')[0])].append(row)
    stability_rows=[]
    for (rank,method,early),rows in sorted(stability.items()):
        stable=sum(r['stable']=='True' for r in rows)
        stability_rows.append(dict(rank=rank,method=method,early_profile=early,runs=len(rows),
            stable=stable,controller_instabilities=len(rows)-stable,numerical_failures=0,stability_rate=stable/len(rows)))
    assert all(r['early_profile']=='min-4096' for r in stability_rows if r['controller_instabilities'])
    write_csv(report/'npg_stability_by_rank.csv',stability_rows)
    ratios_text=', '.join(f"r={r['rank']}: {r['ratio']:.2f}" for r in ratios)
    full=[r for r in control if int(r['rank'])==50 and int(r['stage'])==8]
    full_dense=np.mean([float(r['normalized_gap']) for r in full if r['method']=='dense'])
    full_forced=np.mean([float(r['normalized_gap']) for r in full if r['method']=='forced_rank4'])
    fixed=load_csv(report/'fixed_policy.csv')
    errors={}
    for method in ('dense','known_rank','adaptive'):
        rows=[r for r in fixed if r['n']=='50' and r['r']=='4' and r['tau']=='0.0' and
              r['blocks']=='131072' and r['method']==method and r['ablation']=='both_estimated']
        errors[method]=float(np.mean([float(r['G_error_fro2'])+float(r['Z_error_fro2']) for r in rows]))
    failures=validation['core_outcomes'];numerical=failures.get('numerical_failure',0);unstable=failures.get('controller_instability',0)
    residual_check=json.loads((out/'old-residual-check/summary.json').read_text())
    residual_stable=sum(r['status']=='completed' for r in residual_check['endpoints'])
    residual_medians={m:float(np.median([r['final_g'] if r['final_g'] is not None else np.inf for r in residual_check['endpoints'] if r['method']==m])) for m in ('dense','known_rank','adaptive')}
    rank8data=[json.loads(p.read_text()) for p in (out/'rank8').glob('n*.json')]
    rank8description=[]
    for method in ('dense','known_rank','adaptive'):
        rows=[d for d in rank8data if d['meta']['method']==method]
        stable=sum(d['meta']['status']=='completed' for d in rows)
        success=sum(d['meta']['status']=='completed' and d['rows'][-1]['normalized_gap']<=.1 for d in rows)
        values=[d['rows'][-1]['normalized_gap'] for d in rows if d['rows'][-1]['normalized_gap'] is not None]
        label={'dense':'dense','known_rank':'known rank','adaptive':'adaptive'}[method]
        rank8description.append(f"{label}: stable {stable}/2, target {success}/2, mean g {np.mean(values):.4f}" if len(values)==2 else f"{label}: stable {stable}/2, target {success}/2; failed outputs retained")
    text=fr'''# Final experimental evidence for rank aware stochastic LQR

Joint rank truncation lowers fixed-policy estimation error and improves fixed-output accuracy in the tested low-rank Direct Stein PI family. The comparison uses a common estimator and damped residual update, fixed final policies, and the common target g<=0.1. The final round distinguishes the legacy approximate-greedy PI construction from the requested residual update, diagnoses statistical instability, and reanalyses the existing Stein NPG campaign without new sampled NPG trajectories. Its scope is statistical efficiency within each learning framework; it does not establish an overall advantage over model based CE.

\[
g(K)=\frac{{J(K)-J^\star}}{{J(K_0)-J^\star}},\qquad g(K)\le0.1.
\]

## Direct Stein diagnosis and implementation

The historical first- and second-order Gaussian identities, signs, sigma powers and transposes are correct for the implemented future-state return. The population targets are G_H=B'P_HB and Z_H=-B'P_H(A-BK), with P_H=sum over j=0,...,H-1 of (F^j)'(Q+K'RK)F^j. Subtracting the previous return is valid because the new Gaussian pulse is independent of the pre-pulse history. It reduces a baseline component without making successive blocks independent. H=16 introduces measured finite-horizon bias, rather than an off-by-one error. Nine unit tests cover the identities, continuous sampling, baseline initialization, budget accounting, rank-50 equality, clipping regression and exact checkpoint replay.

Two supplementary failure-path tests verify that numerical failures and unstable controllers keep separate labels, exact executed-budget counters and terminal records. An unstable proposed gain is preserved rather than silently rolled back.

The old dense update constructed C=Ghat K-Zhat, clipped Ghat, and retained the old C. Consequently solve(R+Gclip,C) differs from K-solve(R+Gclip,RK+Zhat) by solve(R+Gclip,(Ghat-Gclip)K). With a projection Pi, the analogous discrepancy is solve(R+Gtilde,(Pi Ghat-Gtilde)K), which also includes cross-subspace leakage. Truncating [G,C] chooses a different empirical subspace from truncating [G,Z]. The legacy construction is a valid approximate-greedy PI estimator under sufficiently accurate block estimates, as used by the manuscript; its non-equivalence to the newly requested update is a protocol mismatch, not a false Stein identity or an invalid PI theorem. The new learner implements the requested residual form: project [G,Z] jointly, clip G in that same subspace, retain RK exactly, and use checked Cholesky solves. The known-rank arm receives r only. The adaptive threshold is ||Mhalf1-Mhalf2||op/2 with fixed multiplier one and block weights (1,1); it is an empirical noise proxy, not a coverage guarantee.

All 24 historical stage-method checks on the four failed 50-dimensional tasks reproduced the archived spectral radii to the declared tolerance. The four tasks share one physical system, two initial policies and two sampling seeds, so this replay is a mechanism diagnosis rather than four independent-system replications. At the historical second-step dense policies, the median raw G and Z squared errors were approximately 107572 and 41752. With undamped residual updates, estimated G plus exact Z still destabilized 4/4 tasks, whereas exact G and exact Z stabilized all four. Estimated Z with exact G destabilized 1/4. Both estimated destabilized 4/4. Damping an already damaged policy was not a complete rescue. These hybrid results identify a real G-estimation failure mechanism along the old trajectories, beyond the choice between two update constructions; they are diagnostics, not model-free performance. Initially, both G and Z noise matter, so the diagnosis is policy dependent.

At those dense second-step policies, median ||F||op is 2.04 and ||P_K||op is 108.87 despite spectral stability, consistent with strong transient amplification. A separate horizon audit finds squared finite-H bias only 0.41 in G and 2.37 in Z at H=16, far below the observed critic errors. Extending the horizon therefore does not address the main failure mechanism. The adaptive historical policies have median ||P_K||op about 3.08. The new protocol applies the requested residual update and common damping from K0; it does not remove the intrinsic G-estimation noise or explain the old failures away by increasing the batch size.

A targeted two-step check starts the new residual update from the actual four historical initial conditions, retaining the old 65536 blocks, H=16, burn1024 and original innovation seeds. The step is the already frozen 0.25, with no retuning. It returns {residual_stable}/12 stable two-step paths across the three variants, but median g remains {residual_medians['dense']:.2f} for dense, {residual_medians['known_rank']:.2f} for known rank and {residual_medians['adaptive']:.3f} for adaptive. Stability at the original failure point therefore does not establish useful accuracy. These four tasks still share one physical system. This check neither establishes eight-step success on that family nor enters the formal eight-system performance table. All outcomes are retained in the separate old-residual-check directory.

## Frozen final PI comparison

The common damped PI step is 0.25, selected and checked on independent pilot systems before the formal run. H=16, sigma=1 and eight updates are fixed. Formal systems 101 through 108 use the validated dense coupled open-loop unstable family, nontrivial SPD Q and R, and an isotropic full-rank K0 with all singular values 0.35. One independent sampling seed is used per system. The pilot and debugging systems are excluded from formal inference. The initial-gap denominator is checked before normalization.

\[
K^+=K-\eta(R+\widetilde G)^{{-1}}(RK+\widetilde Z),\qquad\eta=0.25.
\]

{chr(10).join(table)}

Across 72 formal trajectories, there were {unstable} controller instability events and {numerical} numerical failures. Success and stability denominators include all eight independent systems in every arm and budget cell. Figure B shows the normalized learning curves, system-bootstrap 95% intervals for the median, and the separate success and stability rates. Failed paths remain nonattainments. The sample-to-accuracy table uses the minimum tested budget whose fixed eighth policy succeeds; unmet maximum-budget targets are right-censored. These are grid-based attainments, with no interpolation and no online use of true cost.

![Figure B Direct Stein PI learning curves and success rates]({report.as_posix()}/Figure_B.png)

[Sample to accuracy and censoring table]({report.as_posix()}/sample_to_accuracy.csv) · [Budget comparison figure]({report.as_posix()}/Sample_to_accuracy.png)

Each update counts 512 burn transitions, one initial 16-transition baseline block and N further 16-transition blocks. The core planned {validation['planned_core_transitions']:,} transitions and actually executed {validation['actual_core_transitions']:,}. Pilot, fixed-policy, historical-replay and benchmark costs are listed separately in transition_ledger.csv. Two worker processes each use one numerical thread. The frozen warm pilot forecast was {cfg['two_worker_hours_ideal']:.2f} hours under ideal two-worker scaling, with a 1.5 GB memory plan. {'Observed core wall time was '+format(validation['core_wall_seconds']/3600,'.2f')+' hours.' if validation['core_wall_seconds'] is not None else 'Execution receipts record observed wall time.'} An early resource snapshot measured approximately 306 MiB aggregate resident memory for the core process tree.

## Fixed policy rank dimension and tail evidence

Figure A compares exactly matched raw samples. At n=m=50, r=4 and 131072 blocks, mean joint squared G/Z errors are {errors['dense']:.2f} for dense PSD, {errors['known_rank']:.2f} for known rank and {errors['adaptive']:.2f} for adaptive truncation, across two independent systems. The finite-H bias is separately retained in the numerical table. After actor policies diverge only the exogenous Gaussian innovation scheme is shared; the resulting state trajectories are different.

![Figure A Matched fixed policy critic estimation errors]({report.as_posix()}/Figure_A.png)

Figure C examines ranks 1,2,4,8,16,50, dimensions 25,50,100 at r=4, and total Frobenius tails tau=0,.03,.1. Here tau=||B-B4||F in fixed generator units; each flat tail singular value is tau/sqrt(n-4), and total tail energy is tau². With nonzero tau the 50-dimensional B is algebraically full rank: the rank-4 reference denotes its known head order, not its true algebraic rank. Both ranks are recorded in the fixed-policy table. These small tails remain below the dominant estimation noise in this fixed-policy comparison. This is evidence of robustness at the tested levels, not an identified asymptotic tail floor. The two-system sensitivity comparisons are descriptive. The rank-50 control uses the distinct established nested family and is drawn separately; dense and rank-50 correction coincide bit for bit on all four saved estimates.

![Figure C Rank dimension and total tail sensitivity]({report.as_posix()}/Figure_C.png)

The predeclared rank-8 actor confirmation uses two additional systems, the same step 0.25, eight updates and 131072 blocks per update. Results are {'; '.join(rank8description)}. This small confirmation is reported separately from the eight-system rank-4 inference.

In the full-rank negative control, forcing rank four increases critic error. A separate exact-critic diagnostic makes the bias visible without sampling: after eight common damped PI steps, mean g is {full_dense:.4f} for dense and {full_forced:.4f} for forced rank four. These zero-sample oracle trajectories support the negative-control interpretation and are excluded from model-free sample-efficiency statistics. No 100-dimensional actor or rectangular-action expansion is needed to interpret the central 50-dimensional comparison.

## Stein NPG rank dependence

All 672 archived sampled NPG trajectories are retained, including 98 controller failures. Every such failure belongs to the smaller min-4096 early profile; the min-32768 profiles are all stable. The rank, method and early-budget stability table keeps these conditional rates separate. The common relative target is applied to the fixed final stage-256 output. Reconstructed systems reproduce archived initial costs within rtol=1e-10 and atol=1e-8; cross-platform matrix byte hashes differ, so reproduction is numerical rather than bitwise. The reconstructed arrays are saved. No additional sampled NPG campaign was run.

The actual archived nested generator has nonzero singular values 1.2, hence ||B_r||F²=1.44r. Increasing rank changes the controlled problem. Mean initial gaps increase from {diagnostics[0]['initial_gap_mean']:.2f} at rank one to {diagnostics[-1]['initial_gap_mean']:.2f} at rank 50, while initial spectral radii remain near 0.70. Z signal norm increases, and initial dense critic error relative to Z energy decreases from {diagnostics[0]['raw_noise_to_Z_energy']:.2f} to {diagnostics[-1]['raw_noise_to_Z_energy']:.2f} at the same 32768 blocks. Closed-loop finite-horizon reachability diagnostics are supplied separately.

The exact-critic NPG diagnostic uses the original K0 and original scalar step on all 28 rank-system pairs, with fixed 256 iterations and zero sampled transitions. Rank one needs 43 exact updates to first satisfy g<=0.1; rank 50 needs 13–14. Thus optimization difficulty changes with rank even in the absence of critic sampling noise. Normalization removes a changing gap scale but does not make the optimization problems equivalent: the dense minimum tested budget still falls from {ratios[0]['dense_budget']:,} transitions at rank one to {ratios[-1]['dense_budget']:,} at rank 50. Figure D combines the initial diagnostics, matched-budget critic errors, existing normalized learning curves and fixed-final-policy budget ratios. Dense-to-truncated minimum tested budget ratios under g<=0.1 are {ratios_text}. The ratio criterion requires all four independent systems to succeed at fixed stage 256.

The mean smallest eigenvalue of the initial action curvature R+B'P_K0 B increases from {diagnostics[0]['action_curvature_min_eigenvalue_mean']:.2f} at rank one to {diagnostics[-1]['action_curvature_min_eigenvalue_mean']:.2f} at rank 50. Fewer weakly curved action directions are consistent with the faster exact-critic progress at the unchanged step. This is an optimization diagnostic, not an estimator sample-complexity law.

![Figure D Archived NPG reanalysis at the common precision target]({report.as_posix()}/Figure_D.png)

[Exact critic optimization diagnostic]({report.as_posix()}/NPG_exact_diagnostic.png) · [Rank specific stability table]({report.as_posix()}/npg_stability_by_rank.csv)

## Claims supported by this round

Matched fixed-policy estimates support statistical noise reduction through low-rank postprocessing of a common raw estimator. The final fixed-output PI and archived NPG tables quantify the corresponding finite-grid learning consequences and preserve any nonattainments. The full-rank negative control shows why inappropriate truncation can be harmful. Exact-critic and hybrid trajectories explain mechanisms without being counted as model-free performance. These finite-dimensional, finite-budget results do not establish a universal end-to-end linear rank law, and critic scaling alone is insufficient for such a claim.

| Existing manuscript result | Relevant evidence | Scope of the experimental support |
| --- | --- | --- |
| Direct residual estimation theorem, thm:critic | Archived matched Z-error comparisons and the Stein identity tests | Supports the rank-based noise reduction mechanism for the first-order residual; does not supply a second-order G estimation theorem. |
| Stable rank-aware model-free learning theorem, thm:outer | Fixed-output NPG gains, recorded failures and exact-critic optimization diagnostics | Empirical consequences at the tested schedules; stagewise theoretical confidence certificates and a universal linear rank law are not established. |
| Spectral critic error to PI error proposition, prop:pi | Joint action-block error reduction and the old G-error failure diagnostic | Explains the need for accurate blocks. The proposition uses undamped [G,C] approximate-greedy PI; the new damped [G,Z] residual protocol is an empirical variant, not a literal verification of that construction. |
| Approximate-rank perturbation discussion | Small total-tail comparisons and the full-rank negative control | Supports finite-budget robustness and the risk of truncation bias; no asymptotic tail floor is identified at these small tails. |

The adaptive threshold is empirical and the fixed nominal burn and pilot-selected damping are not implementations of the manuscript's full theoretical certificate. The CE theorem is outside this new sampled round.

## Artifacts and reproduction

Figures A through D are supplied as PNG and editable SVG; NPG exact-critic curves, all system-level tables and the numerical audit are in the report directory. The frozen configuration and source SHA256 manifest identify revision {cfg['source_revision_sha256']}. The workspace has no Git metadata. Historical configurations and archived results remain unchanged. The new independent numerical audit passed: 72 unique core trajectories, exact executed-transition accounting, policy reevaluation, residual checks, four bitwise full-rank estimator identities, 24 historical checks and complete 672-trajectory NPG coverage. Commands and derivations are in FINAL_ROUND_PROTOCOL_20261014.md. All new results, caches and configured temporary files are on E.

- [Frozen configuration]({out.as_posix()}/frozen_config.json)
- [Frozen scientific source manifest]({out.as_posix()}/frozen/SHA256SUMS)
- [Standalone reproduction manifest]({out.as_posix()}/reproduction/SHA256SUMS)
- [Independent numerical audit]({report.as_posix()}/final_audit.json)
- [Primitive transition ledger]({report.as_posix()}/transition_ledger.csv)
- [Core system endpoints]({report.as_posix()}/endpoints.csv)
- [Fixed policy errors and hybrid diagnostics]({report.as_posix()}/fixed_policy.csv)
'''
    target=ROOT/'docs/FINAL_ROUND_REPORT_20261014.md';target.write_text(text,encoding='utf-8')
    (report/'experimental_report.md').write_text(text,encoding='utf-8')
    readme=ROOT/'README.md';existing=readme.read_text(encoding='utf-8')
    marker='Final targeted round (2026-10-14)'
    if marker not in existing:
        line=f'\n{marker}: completed the frozen 72-trajectory Direct-Stein damped PI comparison, six rank-8 confirmations, matched rank/dimension/tail critic diagnostics, and the 672-trajectory NPG reanalysis. Nine frozen learner tests, two supplementary failure-path tests and the independent numerical audit pass. See [final report](docs/FINAL_ROUND_REPORT_20261014.md), [protocol](docs/FINAL_ROUND_PROTOCOL_20261014.md), and [frozen configuration](configs/final_round_20261014.json). Historical sources and results remain preserved.\n'
        first,rest=existing.split('\n',1);readme.write_text(first+'\n'+line+'\n'+rest,encoding='utf-8')
    derived=['scripts/final_round_report.py','scripts/finalize_final_round.py','scripts/final_population_controls.py','scripts/final_horizon_diagnostic.py','scripts/test_final_failure_paths.py','scripts/final_old_residual_check.py','scripts/Run-OldResidualCheck.ps1','scripts/Start-FinalRound.ps1','scripts/Complete-FinalRound.ps1',
             'docs/FINAL_ROUND_REPORT_20261014.md']
    atomic_json(report/'derived_source_hashes.json',{name:sha(ROOT/name) for name in derived})
    # A standalone source tree also includes the old critic's import dependency,
    # even though its LSTD solver is never called by Direct-Stein experiments.
    reproduction=out/'reproduction';all_sources=list(dict.fromkeys(list(cfg['sources'])+derived+['scripts/full_lstd.py','source/project2_paper_body.tex','receipts/final-round-failure-tests-20261014.log','configs/final_round_requirements_20261014.txt']))
    for name in all_sources:
        copy=reproduction/name;copy.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,copy)
    shutil.copy2(out/'frozen_config.json',reproduction/'frozen_config.json')
    (reproduction/'SHA256SUMS').write_text('\n'.join(f'{sha(ROOT/name)}  {name}' for name in all_sources)+'\n',encoding='utf-8')
    return target


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    cfg,verification,ends=audit(a.output);target=publication_report(a.output,cfg,verification)
    print(json.dumps(dict(audit=verification,report=str(target))),flush=True)
