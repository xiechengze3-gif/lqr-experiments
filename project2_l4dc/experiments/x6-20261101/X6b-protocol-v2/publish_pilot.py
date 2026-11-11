"""Append the completed resource PILOT, after a fresh latest-review read."""
import argparse
import datetime
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepared',type=Path,required=True)
    p.add_argument('--resource',type=Path,required=True);p.add_argument('--review-sha256',required=True)
    a=p.parse_args();channel=ROOT.parents[2];task=channel/'CLAUDE_TASK.md'
    assert sha(task)==a.review_sha256
    latest=task.read_text(encoding='utf-8-sig')
    assert 'X6b PROTOCOL v2: ACCEPTED for R2 and resource PILOT' in latest
    assert 'wait for explicit FORMAL acceptance' in latest
    plan=json.loads((a.prepared/'formal-plan.json').read_text())
    config=json.loads((a.prepared/'formal-config.json').read_text())
    assert plan['status']=='PREPARED_AWAITING_EXPLICIT_FORMAL_ACCEPTANCE'
    eq=json.loads((a.resource/'X6b/resource-v1/equivalence/equivalence.json').read_text())
    assert eq['status']=='PASS'
    accounting=sorted((a.resource/'budget').glob('accounting-*.json'))[-1]
    account=json.loads(accounting.read_text());assert abs(account['cumulative_requested_SU']-19)<1e-8
    times=[];resource_transitions=102656
    for n in config['resource_n_values']:
        data=json.loads((a.resource/f'X6b/resource-v1/timing-n{n}/timing.json').read_text())
        assert data['status']=='COMPLETE_RESOURCE_ONLY' and len(data['rows'])==16
        resource_transitions+=data['warmup_primitive_transitions']
        resource_transitions+=sum(r['primitive_transitions'] for r in data['rows'] if r['arm']=='dense')
        seconds=[]
        for alg in ['NPG','PI']:
            r=next(r for r in data['rows'] if r['algorithm']==alg and r['arm']=='dense' and r['rung']==1)
            seconds.append(r['collector_seconds'])
        times.append(f"|{n}|{seconds[0]:.3f}|{seconds[1]:.3f}|{max(r['max_rss_KiB'] for r in data['rows']):,}|")
    allocations=[]
    for n in config['n_values']:
        gs=[g for g in plan['groups'] if g['n']==n]
        allocations.append(f"|{n}|"+' / '.join(str(g['wall_minutes']) for g in gs)+
            f"|{sum(g['requested_bound_SU'] for g in gs):.6f}|")
    for name in ['formal-plan.json','measured-costs.csv']:
        destination=ROOT/name;assert not destination.exists();shutil.copyfile(a.prepared/name,destination)
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    hashes='\n'.join(f'- `{name}` SHA `{digest}`' for name,digest in config['scientific_sources'].items())
    coverage=('Full four-dimension grid fits; no cuts proposed.' if not plan['proposed_omitted_dimensions'] else
              'Full four-dimension request does not fit400SU. Per registered cut order, PROPOSE omitting '+
              str(plan['proposed_omitted_dimensions'])+'; see alternatives in formal-plan.json. Await approval of this concrete scope.')
    text=f'''

## X6b PILOT

All5 resource allocations complete:20365427 equivalence,20365428/29/30/31 for
n24/36/48/72. Frozen collector/actor equivalence PASS for both NPG and PI,
bitwise assessed gains/results and exact primitive counts, including absorbing
padding. Resource-only timings cover all32(n,rung,algorithm) cells and both
updates/artifact writes. No noisy accuracy/gap/rho/projection readout.

R2 remains NPG16 / PI8 at eta0.2; bases524288/1048576/2097152/4194304,
H16,nu1,burn16pulseblocks+baseline1. All4rungs1/64,1/16,1/4,1 fit for
proposed dimensions{config['n_values']}. Systems301-308 x fresh sampling seeds1701-1704,
no systems/seeds/rungs removed within included dimensions. {coverage}
Integer schedules remain byte-for-byte as
resolved-v1; primitive equality holds between arms and algorithms.

Largest-stage single-collector timings at rung1 (seconds; the FORMAL estimate
uses TWO independent collectors, both updates/writes):

|n|NPG seconds|PI seconds|max RSS KiB|
|---:|---:|---:|---:|
{chr(10).join(times)}

Measured FORMAL proposal:{len(plan['groups'])}arrays x32tasks={plan['tasks']}allocations,
{int(plan['paired_paths'])}paired paths /{int(plan['arms'])}arms,
{plan['training_primitive_transitions']} primitive transitions including all burn/baseline.
Per(n,system,seed), bundle the low3rungs x2algorithms; full-rung NPG and PI
remain separate allocations. Every scientific path has a fresh K0/state and its
registered private RNG; bundling reuses only immutable plant data. Same plant
NPZ bytes across arms/rungs/algorithms, hashed registry{len(config['model_registry'])}models; no old formal
performance used. Threads1,1CPU/2GiB; short<=120min,medium otherwise
(live queue limits2h/24h). No automatic retry.

Forecast sums each exact integer schedule plus burn/baseline, using its measured
max-stage collector rate, TWO arms, measured updates/writes,1s per arm/stage
evaluation/checkpoint allowance,60s allocation startup/cache allowance, then
30% margin and integer-minute ceilings. Actual cost may differ from this forecast.

|n|minutes per task:low3 /fullNPG /fullPI|32tasks per group,requested SU|
|---:|---:|---:|
{chr(10).join(allocations)}

FORMAL requested upper **{plan['formal_requested_SU']:.6f}SU**; reserve REPORT
**6.5SU** (four90min saved-data diagnostic jobs +one30min aggregate job),
zero new report transitions. With prior19SU, cumulative upper
**{plan['total_requested_with_report_SU']:.6f}/400SU**. {coverage}
Resource PILOT itself requested1.916666667SU, primitive transitions
{resource_transitions:,} including separate warmups and both equivalence versions.

Shallow reviewer files: `experiments/x6-20261101/X6b-protocol-v2/formal-plan.json`
and `measured-costs.csv` (all32 measured cells). Executable config/32model copies
under `prepared-formal-v1/`; config SHA `{plan['formal_config_sha256']}`.
Resource delivery is locally archive/per-file SHA verified, scope includes all
timings, equivalence proof, raw artifacts, receipts, logs and accounting.

Frozen analysis: failure-inclusive full32 endpoint/stage median/IQR; both-stable
and failure-inclusive paired ratios, all failures/denominators; common5000
system-cluster draws; observed-rung29/32 attainment for relative0.1/0.05 with
right censoring and censored bootstrap mass. D/action-gap decomposition and
own-preupdate-policy rho/projection diagnostics are simulator-only, never
learner inputs. Raw/clipped/compressed PI diagnostics are separated. All raw
stage/checkpoint hashes, K continuity, updates, primitive counts are audited.
Plots read CSV only. Numerical report runs on compute nodes,0new samples.

{hashes}

**No FORMAL job has been submitted. Await explicit X6b FORMAL ACCEPTED.**
Old data/results/releases and paper TeX unchanged; X6c remains deferred.
Review reread {now},task SHA `{a.review_sha256}`.
X6 cumulative requested19/400SU; Slurm elapsed
{account['slurm_elapsed_billing_SU']:.9f}SU, AMS settled
{account['ams_settled_walltime_slots_SU']:.9f}SU at{account['checked_utc']}
(overlapping views; never add).

STATUS: PILOT DONE X6b
'''
    report=ROOT/'PILOT_REPORT.md';assert not report.exists()
    report.write_text(text.lstrip(),encoding='utf-8')
    assert sha(task)==a.review_sha256,'Review changed; reread before publishing.'
    with (channel/'CODEX_REPLY.md').open('a',encoding='utf-8',newline='') as stream:stream.write(text)
    print(json.dumps(dict(status='PILOT_POSTED_AWAITING_FORMAL_ACCEPTANCE',
        report_sha256=sha(report),formal_requested_SU=plan['formal_requested_SU'],
        cumulative_with_report_SU=plan['total_requested_with_report_SU'])))


if __name__=='__main__':main()
