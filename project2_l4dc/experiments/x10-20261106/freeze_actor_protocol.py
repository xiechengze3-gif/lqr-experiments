"""Freeze the explicitly authorized X10b pilot without submitting or simulating."""
import ast
import datetime
import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE/'actor-draft-v2'
CHANNEL = HERE.parents[1]
EXPECTED = 'df87773e90d06e4ffa5ae4d5c0c9318c8f5ca2e3336e9be142d6b7f42101efb7'
NAME = 'x10-20261106-b-pilot-v1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def main():
    review = (CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert sha(review) == EXPECTED
    assert 'X10b — bounded pilot AUTHORIZED, cap clarified' in review.decode('utf-8-sig')
    prior = (CHANNEL/'CODEX_REPLY.md').read_bytes()
    assert b'## X10b PROTOCOL' not in prior
    config = json.loads((ROOT/'actor-config-draft-v2.json').read_text())
    assert config['n_values'] == [72, 48, 36, 24]
    assert config['new_formal_paired_paths'] == 1280
    assert config['new_formal_primitive_transitions'] == 243008280576
    names = ['frozen_engine.py', 'estimation.py', 'actor_paths.py', 'formal_driver.py',
             'analyze_actor.py', 'plot_saved_actor.py', 'actor_pilot.py']
    for name in names+['remote_actor.py']:
        ast.parse((ROOT/name).read_text(encoding='utf-8'), filename=name)
    spec = importlib.util.spec_from_file_location('stdlib_globals_checker', HERE/'prepare_ce_v2.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    for name in ['actor_pilot.py', 'remote_actor.py']:
        assert not checker.global_name_audit((ROOT/name).read_text(), name), name
    config.update(status='PROTOCOL_FROZEN', version=1,
        scientific_sources={name: sha((ROOT/name).read_bytes()) for name in names},
        actual_forecast_cap_SU=160, requested_upper_cap_SU=200,
        report_reserve_SU=8, global_concurrency=8,
        author_review_sha256=EXPECTED, pilot_requested_upper_SU=4+1/6,
        pilot_after_X9_last_array='20413893',
        formal_resource_rule='max(historical per-cell worst five-rung body, measured n72 five-rung body scaled by historical worst dimension profile); requested limit ceil((1.20*body+30)/60) min',
        formal_actual_forecast_rule='32 times each resolved per-(n,algorithm) body seconds /3600 plus completed pilot Slurm cost (or its bound) and 8 SU report reserve',
        formal_requested_rule='all resolved task limits plus cumulative pilot requests and 8 SU report reserve; <=200',
        formal_order=[g['id'] for g in config['formal_groups']],
        formal_gate='All saved-record equivalence/resource/RSS checks PASS; actual forecast<=160, requested upper<=200; deadline feasible at global<=8; then automatic')
    for meta in config['model_registry'].values():
        assert sha((ROOT/meta['path']).read_bytes()) == meta['sha256']
    cost = json.loads((HERE/'SOURCE_AND_COST_AUDIT_v1.json').read_text())
    old_body_forecast = 32*sum(c['provisional_body_seconds'] for c in cost['cells'])/3600
    old_requested = cost['formal_requested_upper_SU']
    config['historical_resource_profile'] = cost['cells']
    config['provisional_actual_forecast_SU'] = old_body_forecast+4+1/6+8
    config['provisional_requested_upper_SU'] = old_requested+4+1/6+8
    assert config['provisional_actual_forecast_SU'] <= 160 and config['provisional_requested_upper_SU'] <= 200
    config_path = ROOT/'actor-config-protocol-v1.json'
    new(config_path, (json.dumps(config, indent=2)+'\n').encode())
    table = '\n'.join(f"|{entry['n']}|{entry['rung']:g}|{entry['primitive_per_arm_per_algorithm']}|"
                      for entry in config['all_schedules'])
    source_table = '\n'.join(f'|{name}|{digest}|' for name, digest in config['scientific_sources'].items())
    protocol = f'''# X10b PROTOCOL v1 — new actor rungs only

Authority: X10 GO plus explicit00:35CDT11/06 bounded-pilot authorization/cap clarification, review SHA `{EXPECTED}`. This supersedes the initial requested-cost stop: actual-spend forecast cap160SU; requested allocation upper may reach200SU for fixed guards/rounding. No new science claim, no theorem verification, no outcome-based cuts/tuning, no automatic retry. Old results/releases/docs/paper tex remain untouched.

Family S and every X6b ingredient frozen except the new rung: n=m72/48/36/24, exactrank2, original models/bytehashes/systems301–308,seeds1701–1704;eta.2,nu1,H16,16pulseburn+1baselineblock,16NPG/8PIstages. Original one continuous path per arm/rung, old RNG namespace excludesarm/rung, same paired exogenous Gaussian draws. N_cal values and scalar stage growth/PIinteger matching exactly the original schedules function. Newrungs1/256,1/128,1/32,1/8,1/2; old1/64,1/16,1/4,1 reused by reference in full including failures. All old outputs stay byte-identical and are not rerun as scientific replications.

Formal order **n72,n48,n36,n24**, each NPG then PI,all five new rungs bundled per task;8arrays×32tasks,1280pairedpaths2560arms,243008280576newphysicaltransitions. Both arms count burn/baseline/failure padding exactly. Truth-based instability is absorbing failure only, withK0padding consuming the rest; no recovery/earlier-iterate selection. Hard failures stop/report, no automatic resubmission or invented partial count. Model truth only in simulation/evaluation; learners receive only fixed original observation/cost/order inputs. No critic/LSTD/new ridge/whitening/damping.

Source adaptation check: kernel/estimation unchanged, actor checkpoint wrapper changes only its allowed output namespace; formal driver changes output namespace and experiment descriptor; analyzer changes namespace only. Reversing those changes yields original source text. Scalar schedule extraction ran only integer arithmetic; no model solve, trajectory, estimate or numerical diagnostic has run for X10b. Copied32 frozen model binaries verify originalSHA. The old Windows-only plot script is retained as an unused source reference; a new saved-CSV presentation wrapper will use the combined table, with no changed statistic.

|n|new rung|primitive transitions per arm, either algorithm|
|---:|---:|---:|
{table}

Bounded PILOT exactly authorized: one1CPU/2GiB/10min equivalence job, then two1CPU/2GiB/120min timing jobs (oneNPG,onePI), requested total4.166667SU. Equivalence dependsafterokX9lastformalarray20413893; timing jobs dependafterokequivalence. This serial check prevents spending on timing after a failed implementation check. At most two timing jobs overlap plusX9report1core, belowglobal8; no X10b formal before all X9 compute jobs have finished, to preserve coordination.

Equivalence: exactly saved n24,s301,seed1701,rung1/64,bothalgorithms; original model bytes and savedspec copied, new validation-only outputroot. Require entire records dictionaries, all saved stage arrays (Kbefore/behavior/Kafter/Ghat/Zhat/xafter), RNG states, transition/padding counts **bitwise identical** to original receipts. This sole deliberate replay is the explicitly requested validation exception, labelednotanewformalreplication. Never choose a different old path or relax a failed tolerance. No gap/stability/performance is printed or used for selection. Every physical replay transition is counted.

Timing: disjoint n72 resource system9102,seed9801,all5newrungs,botharms,onealgorithmperjob. Use unchanged F587model and actor. Read out runtime,RSS,source/receipt hashes and transition counts only. Require process peakRSS<=80%of2GiB; full timing path/checkpoint costs included. Per-task requested guard is frozen **1.20×body+30s**, rounded up to minutes. Pilot timing role finishes only after all5rungs with fixed counts; allpartial/checkpointfiles retained if interrupted.

Beforeformal, form each(n,algorithm) body prediction as the max of (i) historical worst full-rung task runtime times0.66796875, (ii) measured n72five-rung body scaled by the same algorithm's historical worst dimension profile. This extrapolates currentmeasurement while retaining a historical worst-case floor; no gap is used. Actual-spend forecast=32times each resolvedcellbody/3600 +completedpilotSlurmSU(or itsbound)+8SUreportreserve, must<=160. Requested upper=sum32times rounded guardedlimits/60 +cumulativepilotrequests+8reportreserve, must<=200. Current **unmeasured** historical-floor figures are actualforecast{config['provisional_actual_forecast_SU']:.6f}SU andrequestedupper{config['provisional_requested_upper_SU']:.6f}SU. These are forecasts, not consumedSU. Post measured limits/hashes/spend beforeautomaticformal; if either cap/RSS/check/deadlinecondition fails,stop/report, no grid/seed/rung cut.

Current provisional formal allocation envelope at8cores is{old_requested/8:.3f}h of running time, plus remaining X9time,up to2h10minpilot,report/queues. This fits theNov8 18CT target under ordinary queues; no reservation/queueguarantee or concurrency increase. Resolved forecast is rechecked against the remaining deadline afterpilot. Checkcurrentmyproject/ownqueue/billingbeforeevery submission; maintain separateactual/forecast/requestedledger, durable reservations beforeSBATCH, reconcile uncertain responses instead of replaying. Keep existing mainSSH/PuTTY/VPN untouched.

REPORT: exactly originalX6bstatistics/bootstrap/failure definitions for the5newrungs, allstablecounts/firstfailures/padding/absolute+relativegapmedian/IQR/bothpairedratiodefinitions/clusterCI, rawfieldsfull32. New-only summary.csv exact originalschema; mergednine-rung copy appendsnewrows tooriginalCSVbytes, verifyoldprefixbyte-identical. No rebootstrap/recomputeexistingrows. Derive median-curve transitions-to-matchfullrungdensegap withsame papercross arithmetic on nine rungs, originalfour-rung derivedvalues separatelyforcomparison, allleft/right/unidentifiedcensorflags. Full-failureCSV, allpolicies/checkpoints/model/config/source hashes preserved. No newepsilon/theoremclaim. REPORTreserve8SU: fourdimensionaudits up to90mineach (6SU),aggregate/plots/pack up to120min (2SU), oneCPU2GiB each,global<=8. Analysisusesonlysaveddata,notnewtraining.

Allnumericalwork onGraceSlurmcompute, login-onlymetadata/deployment. Newroot `/scratch/user/changze/lqr_experiments/results/x10-20261106/X10b`; explicitcache/tmpunderx10-20261106,oneBLAS/OpenMP/Numbathread. Existing3.11environment,noinstallation. Localsource/package/resultrootonE. X10a locally uses0GraceSU separately; X9 remains separatecap50.

Config SHA256 `{sha(config_path.read_bytes())}`.

|source|SHA256|
|---|---|
{source_table}

PreparedbeforeanyX10b numericalexecution; newjobs0,requested/actualspend0/0SU. Resourcepilotexplicitlyauthorized,formalonlyafterthefixedconditionsabove.
'''
    new(ROOT/'PROTOCOL_v1.md', protocol.encode())
    new(ROOT/'CLAUDE_TASK_AUTHORIZED.md', review)
    approval = dict(experiment='X10b', stage='PILOT', review_sha256=EXPECTED,
                    exact_authorization_heading='X10b — bounded pilot AUTHORIZED, cap clarified',
                    protocol_sha256=sha(protocol.encode()), config_sha256=sha(config_path.read_bytes()),
                    actual_forecast_cap_SU=160, requested_upper_cap_SU=200,
                    pilot_requested_upper_SU=4+1/6)
    new(ROOT/'approval.json', (json.dumps(approval, indent=2)+'\n').encode())
    shell = '''#!/usr/bin/env bash
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$base/releases/x10-20261106-b-pilot-v1
cache=$base/cache/x10-20261106
temp=$base/tmp/x10-20261106/job-${SLURM_ARRAY_JOB_ID:?}-${SLURM_ARRAY_TASK_ID:?}
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B actor_pilot.py --config actor-config-protocol-v1.json --role __ROLE__
'''
    for role in ['equivalence', 'NPG', 'PI']:
        new(ROOT/f'pilot-{role}.sbatch', shell.replace('__ROLE__', role).encode())
    paths = [ROOT/name for name in names+['remote_actor.py', 'actor-config-protocol-v1.json',
             'PROTOCOL_v1.md', 'CLAUDE_TASK_AUTHORIZED.md', 'approval.json']]
    paths += list((ROOT/'baseline').rglob('*'))
    paths += [ROOT/f'pilot-{role}.sbatch' for role in ['equivalence', 'NPG', 'PI']]
    paths = [p for p in paths if p.is_file()]
    hashes = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in paths}
    sums = ''.join(f'{digest}  {name}\n' for name, digest in hashes.items()).encode()
    new(ROOT/'SHA256SUMS', sums)
    paths.append(ROOT/'SHA256SUMS')
    archive = HERE/'packages'/(NAME+'.tar.gz')
    archive.parent.mkdir(exist_ok=True)
    assert not archive.exists()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes() == review
    with tarfile.open(archive, 'x:gz') as tf:
        for path in paths:
            payload = path.read_bytes()
            member = tarfile.TarInfo(path.relative_to(ROOT).as_posix())
            member.size = len(payload)
            tf.addfile(member, io.BytesIO(payload))
    manifest = dict(status='PROTOCOL_FROZEN_PILOT_AUTHORIZED_NOT_SUBMITTED',
                    created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    approval=approval, files=hashes, SHA256SUMS_sha256=sha(sums),
                    archive=str(archive), archive_sha256=sha(archive.read_bytes()),
                    new_jobs=0, new_SU=0)
    new(HERE/'ACTOR_PROTOCOL_MANIFEST_v1.json', (json.dumps(manifest, indent=2)+'\n').encode())
    section = ('\n\n## X10b PROTOCOL\n\n'+protocol.split('\n', 1)[1].lstrip().replace('\n## ', '\n### ')
        +'\nFiles: `experiments/x10-20261106/actor-draft-v2/PROTOCOL_v1.md`, frozenconfig/sources/models/SHA256SUMS; '
        '`ACTOR_PROTOCOL_MANIFEST_v1.json` and immutable pilotpackage. Scalar/source/hash checks PASS; numericalpilotpending. '
        'Submitting only your authorized4.166667SUboundedpilot withdependencyafterX9lastarray, noformaluntilallgatespass.\n\n'
        'STATUS: PROTOCOL DONE X10b\n').encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes() == review and (CHANNEL/'CODEX_REPLY.md').read_bytes() == prior
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:
        stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes() == prior+section
    new(HERE/'ACTOR_PROTOCOL_APPEND_RECEIPT_v1.json', (json.dumps(dict(
        prior_bytes=len(prior), appended_bytes=len(section), prior_preserved=True,
        review_sha256=EXPECTED), indent=2)+'\n').encode())
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}))


if __name__ == '__main__':
    main()
