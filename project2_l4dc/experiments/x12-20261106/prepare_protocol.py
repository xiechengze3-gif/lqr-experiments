"""Freeze X12 protocol, immutable kernel identity, calibration-only submission."""
import hashlib, json, tarfile
from pathlib import Path
R=Path(__file__).resolve().parent;C=R.parents[1];OLD=R.parent/'x10-20261106/prepared-actor-formal-v1'
D=R/'pilot-release-v1';D.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,s):
    with p.open('xb') as f:f.write(s if isinstance(s,bytes) else s.encode())
review=(C/'CLAUDE_TASK.md').read_text(encoding='utf-8');review_sha=sha(C/'CLAUDE_TASK.md')
assert 'X11 + X12 GO and CONCURRENCY (13:15 CDT 11/06)' in review
put(D/'CLAUDE_TASK_AUTHORIZED.md',(C/'CLAUDE_TASK.md').read_bytes())
for name in ['frozen_engine.py','estimation.py']:put(D/name,(OLD/name).read_bytes())
assert sha(D/'frozen_engine.py')=='9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989'
assert sha(D/'estimation.py')=='f587bd48993288dbf9160dd4cc1e62542f15ee5794bda37590ec48dc672c9c59'
actor=(OLD/'actor_paths.py').read_text();old='/results/x10-20261106/X10b';new='/results/x12-20261106'
assert actor.count(old)==1
put(D/'actor_paths.py',actor.replace(old,new))
assert (D/'actor_paths.py').read_text().replace(new,old)==actor
put(D/'pilot_driver.py',(R/'pilot_driver.py').read_bytes())
proof=dict(engine_byte_identical=True,estimator_byte_identical=True,
    engine_sha256=sha(D/'frozen_engine.py'),estimator_sha256=sha(D/'estimation.py'),
    original_actor_sha256=sha(OLD/'actor_paths.py'),actor_sha256=sha(D/'actor_paths.py'),
    actor_numerical_source_literal_identity=True,only_actor_edit=dict(old=old,new=new,purpose='fresh output namespace guard'),
    previous_X10b_verified_source=str(OLD),new_replay_not_needed_by_author_GO=True)
put(D/'SOURCE_IDENTITY.json',json.dumps(proof,indent=2))
grid=[2048,8192,32768,131072,524288,2097152,4194304]
old_cfg=json.loads((R.parent/'x6-20261101/amendment-A1/config-X6a-v2.json').read_text())
assert grid==old_cfg['stein_blocks_by_n']['48']==old_cfg['stein_blocks_by_n']['72']
cfg=dict(experiment='X12',n=60,m=60,rank=2,eta=.2,H=16,nu=1.,burn_blocks=16,NPG_T=16,PI_T=8,
    calibration_systems=[9101,9102],calibration_seeds=[9601,9602,9603,9604],calibration_grid=grid,
    calibration_rule='smallest_registered_N_with_median_of_two_system_four_seed_medians_dense_Z_rho_op_le_1',
    calibration_grid_provenance='identical preregistered n48 and n72 high-dimension X6a A1 grid, bracketing new n60; no inserted rung',
    rungs=[1/256,1/128,1/64,1/32,1/16,1/8,1/4,1/2,1.],formal_systems=list(range(301,309)),formal_sampling_seeds=[1701,1702,1703,1704],
    timing_system=9102,timing_seed=9801,actual_cap_SU=230,requested_cap_SU=300,global_concurrency=64,automatic_retries=0,
    pilot_calibration_requested_SU=8*20/60+5/60,pilot_timing_requested_SU=6,report_reserved_SU=8,
    review_sha256=review_sha,sources={name:sha(D/name) for name in ['frozen_engine.py','estimation.py','actor_paths.py']},driver_sha256=sha(D/'pilot_driver.py'))
put(D/'config-protocol-v1.json',json.dumps(cfg,indent=2))
protocol='''# X12 n=m60 NPG / PI

Author GO13:15 CDT Nov6. Same X6b S family/certificate/streams/rank2,
eta.2,H16,nu1,burn16+baseline1 each update,NPG16/PI8 stages. Dense RK term
retained in NPG; PI joint left compression/PSD clipping unchanged. Preserve
all absorbing learning failures, their padding budgets and infinity gaps.
No critic/LSTD/recovery/line search/oracle input/rank adaptation.

Kernel and estimator hashes are byte-identical to X10b verified sources.
actor_paths numerical source is literal identical; the one path guard changes
to a fresh X12 namespace and an inverse replacement proves identity. Full
actor file hash therefore differs; this is disclosed. No duplicate replay.

CALIBRATION pilot: systems9101/9102,seeds9601..9604,K0=0; exact frozen Stein
collector/state/RNG/chunk/prefix summation. Grid2048/8192/32768/131072/524288/
2097152/4194304, exactly the registered n48 and n72 grids bracketing n60.
No extra1048576 rung, no formal/truncated/actor readout enters selection.
For eachN, median4seeds per system, then median2systems of dense
||Zhat-Z||op/sigma2(Z). Select smallest registeredN with value<=1. Censored
at4194304 => stop/report, no extension. All8paths run their entire fixed grid.
8oneCPU/2GiB/20min tasks plus1five-min resolution job, requested2.75SU,
536873088primitive calibration transitions, no implicit retries.

Global slot reservation: X10b is two independent lanes of<=32 each. Calibration
array<=8 depends on successful completion of the original first8 n72PI tasks
20416268_0..7. They have no lane1 successor and cannot rerun here. Thus their
completion permanently leaves at least8slots: remainingPI<=24 + otherlane32
+calibration8<=64. Resolution waits for whole calibration and uses1slot.
Every later submission accounts for all extant reserved slots, not merely a
momentary running count. No changes to X10b tasks or frozen configs.

TIMING pilot: disjoint pilot system9102,seed9801, both algorithms/arms,
all9rungs at selectedbase; original integer schedules and exact primitive
parity. Two1CPU/2GiB/180min tasks, requested6SU, only after calibration PASS.
Record full body/wall seconds and peakRSS; no outcome-dependent grid choice.
Checks: kernel/estimator/literal actor identity; calibration coverage/criterion;
all18paired paths/counts/RNG/source receipts; memory<80%of2GiB; Slurm billing1.
Stop/report on hard error, censoring or failed fixed check. Never automatic retry.

FORMAL automatically iff all fixed checks PASS and measured forecast
actual<=230SU/requestedupper<=300SU including all pilot and8SU reportreserve.
Forecast32times each algorithm's full9rung pilot body, plus pilots/report;
wall guards ceil((1.2*body+30)/60) minutes per task. If historical comparable
per-transition runtime yields a larger forecast, keep the larger. Resource
pilot has not happened yet, so there is NO current formal-cost assertion.
Formal systems301..308 xseeds1701..1704, all9rungs, bothalgorithms/arms,
64allocationtasks/576pairedpaths/1152arms. Choose only scheduling throttle
to preserve global64; no science or count changes. No formal observations yet.

REPORT schema exactly X6b summary.csv, append n60 to complete X6b+X10b9rung
table, original matching-budget cross arithmetic transitions_saved_derived.csv.
All failure denominators, censoring, pairing and bootstrap routines unchanged.
Copy every completed raw bundle promptly to E with archive/member SHA checks.
Old datasets used only from verified local copies; no dependency on purged
remote X6b. Descriptive, no theorem verification or epsilon-attainment claim.
No old results/frozen releases/paper edits. Read review log before each stage.
'''
put(D/'PROTOCOL.md',protocol);put(R/'PROTOCOL_v1.md',protocol)
base='/scratch/user/changze/lqr_experiments';release='x12-20261106-pilot-v1'
template='''#!/usr/bin/env bash
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$base/releases/x12-20261106-pilot-v1
cache=$base/cache/x12-20261106
temp=$base/tmp/x12-20261106/job-${SLURM_JOB_ID:?}-${SLURM_ARRAY_TASK_ID:-na}
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TMP="$temp" TEMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B pilot_driver.py --config config-protocol-v1.json --role __ROLE__ __EXTRA__
'''
for role in ['calibration','resolve','NPG','PI']:
    put(D/(role+'.sbatch'),template.replace('__ROLE__',role).replace('__EXTRA__','--index "$SLURM_ARRAY_TASK_ID"' if role=='calibration' else ''))
put(D/'SHA256SUMS',''.join(sha(p)+'  '+p.name+'\n' for p in sorted(D.iterdir()) if p.is_file()))
package=R/'x12-20261106-pilot-v1.tar.gz'
with tarfile.open(package,'x:gz') as tf:
    for p in sorted(D.iterdir()):tf.add(p,arcname=release+'/'+p.name)
manifest=dict(archive_sha256=sha(package),archive_bytes=package.stat().st_size,review_sha256=review_sha,release=release,
    config_sha256=sha(D/'config-protocol-v1.json'),source_identity=proof,pilot_calibration_requested_SU=2.75,
    files={p.name:sha(p) for p in D.iterdir() if p.is_file()})
put(R/'PROTOCOL_MANIFEST_v1.json',json.dumps(manifest,indent=2))
with (C/'CODEX_REPLY.md').open('a',encoding='utf-8') as f:
    f.write('\n## X12 PROTOCOL\n\n'+protocol+'\nFull registry/source identity/package hashes in experiments/x12-20261106/PROTOCOL_MANIFEST_v1.json.\nSTATUS: PROTOCOL DONE X12\n')
print(json.dumps(dict(status='PROTOCOL_FROZEN',review_sha256=review_sha,archive_sha256=manifest['archive_sha256'],calibration_requested_SU=2.75,formal_not_submitted=True)))
