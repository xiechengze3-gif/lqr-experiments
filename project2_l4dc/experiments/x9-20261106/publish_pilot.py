"""Stdlib metadata/resource checks, measured formal plan and append-only PILOT delivery."""
import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
EXPECTED_REVIEW = 'fa9c096667a147ed70a135eb9fcc415e9e6e00f3e71f0c0957f00f825352201a'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, indent=2)
        stream.write('\n')


def main():
    task = CHANNEL/'CLAUDE_TASK.md'
    assert sha(task) == EXPECTED_REVIEW, 'Read the new review before advancement.'
    reply = CHANNEL/'CODEX_REPLY.md'
    prior = reply.read_bytes()
    assert b'## X9 PILOT' not in prior
    config_path = HERE/'config-protocol-v1.json'
    cfg = json.loads(config_path.read_text())
    for name, digest in dict(cfg['scientific_sources'], **cfg['baseline_sources']).items():
        assert sha(HERE/name) == digest
    delivery = json.loads((HERE/'PILOT_DELIVERY_VERIFIED_v1.json').read_text())
    assert delivery['files'] == 70
    times = [json.loads((HERE/'pilot-delivery-v1/resource-v1'/f'task-{i}/timing.json').read_text())
             for i in range(4)]
    for index, t in enumerate(times):
        assert t['status'] == 'COMPLETE_RESOURCE_ONLY' and t['index'] == index
        assert t['config_sha256'] == sha(config_path)
        assert t['source_sha256'] == cfg['scientific_sources']['x9_core.py']
        assert t['formal_observation_transitions'] == 0 and t['no_performance_readout']
        assert t['primitive_transitions'] == 503421344
        assert all(c['status'] == 'PASS_BITWISE_GAINS_COLLECTOR_RNG_COUNTS' for c in t['equivalence'])
        assert len(t['equivalence']) == 2 and len(t['rows']) == 4
    progress_path = sorted(HERE.glob('pilot-progress-*.json'))[-1]
    progress = json.loads(progress_path.read_text())
    allocations = []
    slurm_rss = []
    for line in progress['sacct'].splitlines():
        job, state, elapsed, cpus, rss, tres = line.split('|')[:6]
        if '.' in job:
            if rss.endswith('K'):
                slurm_rss.append(float(rss[:-1]))
            continue
        assert state == 'COMPLETED' and int(cpus) == 1
        parsed = dict(p.split('=', 1) for p in tres.split(',') if '=' in p)
        assert float(parsed['billing']) == 1
        allocations.append(dict(job=job, elapsed_seconds=int(elapsed), billing_cores=1))
    assert len(allocations) == 4
    elapsed_su = sum(r['elapsed_seconds'] for r in allocations)/3600
    accounting = json.loads((HERE/'PILOT_ACCOUNTING_v1.json').read_text())
    assert not accounting['own_X9_AMS_rows'], 'AMS now has rows: parse them explicitly rather than report pending.'
    estimates = {}
    for alg in ['NPG', 'PI']:
        cases = [t for t in times if t['case']['algorithm'] == alg]
        estimates[alg] = dict(
            full=max(next(r['seconds'] for r in t['rows'] if r['rung'] == 1) for t in cases),
            low_three=max(sum(r['seconds'] for r in t['rows'] if r['rung'] < 1) for t in cases))
    predicted = {'n24-low-three': estimates['NPG']['low_three']+estimates['PI']['low_three'],
                 'n24-full-NPG': estimates['NPG']['full'], 'n24-full-PI': estimates['PI']['full']}
    peak = max([t['peak_RSS_KiB'] for t in times]+slurm_rss)
    headroom = 1-peak/(2*1024*1024)
    groups = []
    for group in cfg['formal_groups']:
        original_id = group['id'].split('-', 1)[1]
        wall = 8 if original_id == 'n24-low-three' else 7
        seconds = predicted[original_id]
        groups.append(dict(id=group['id'], alpha=group['alpha'], tasks=32, cpus=1,
                           memory_MiB=2048, wall_minutes=wall, requested_bound_SU=32*wall/60,
                           predicted_body_seconds=seconds, guarded_seconds=1.2*seconds+30,
                           wall_guard_pass=1.2*seconds+30 <= wall*60))
    formal_su = sum(g['requested_bound_SU'] for g in groups)
    all_pass = all(g['wall_guard_pass'] for g in groups) and headroom >= .2
    assert all_pass and abs(formal_su-46.93333333333333) < 1e-10
    registry = {}
    for t in times:
        key = str(t['case']['prepare_alpha'])
        registry[key] = t['formal_model_registry']
        assert set(registry[key]) == {str(s) for s in cfg['formal_systems']}
        for system, meta in registry[key].items():
            remote = Path(meta['path']).as_posix()
            prefix = '/scratch/user/changze/lqr_experiments/results/x9-20261106/'
            assert remote.startswith(prefix)
            local = HERE/'pilot-delivery-v1'/remote[len(prefix):]
            assert sha(local) == meta['sha256']
            assert meta['certificate']['r'] == 24 and meta['certificate']['retained_order'] == 2
    assert len(registry) == 4
    formal = dict(cfg, status='FORMAL_FROZEN', model_registry=registry,
                  resource_pilot_archive_sha256=delivery['archive_sha256'])
    formal_path = HERE/'prepared-formal-v1/formal-config.json'
    new(formal_path, formal)
    plan = dict(status='RESOURCE_CHECKS_PASS_WAITING_CLAUDE_PILOT_ACCEPTED',
                cap_SU=50, pilot_requested_SU=1, pilot_completed_Slurm_elapsed_SU=elapsed_su,
                AMS_settlement='PENDING_NO_OWN_ROWS_AT_SNAPSHOT',
                formal_requested_SU=formal_su, report_reserve_SU=2,
                cumulative_requested_upper_SU=1+formal_su+2, groups=groups,
                global_concurrency=8, array_order='sequential afterok; no overlapping arrays',
                estimated_formal_body_hours_at_8cores=4*32*sum(predicted.values())/3600/8,
                requested_formal_running_hours_at_8cores=formal_su/8,
                peak_RSS_KiB=peak, memory_headroom_fraction=headroom,
                formal_config_sha256=sha(formal_path), automatic_retries=0,
                new_formal_transitions=128849584128,
                pilot_primitive_transitions=sum(t['primitive_transitions'] for t in times))
    new(HERE/'prepared-formal-v1/formal-plan.json', plan)
    rows = []
    for t in times:
        rows.append(f"|{t['index']}|{t['case']['alpha']}|{t['case']['algorithm']}|"
                    +'/'.join(f"{r['seconds']:.3f}" for r in t['rows'])
                    +f"|{t['peak_RSS_KiB']}|PASS (both alpha0 and positive alpha)|")
    report = f'''# X9 PILOT

Resource-only array20413460: all4 COMPLETED, no retry. All8 comparisons PASS bitwise gains/collector outputs/RNG/counts. No gap/stability/performance was read out or used for selection. The full4-rung real actor paths were timed; controls, pairing and integer schedules are unchanged. Each task used503421344 primitive transitions including equivalence/reference work; total2013685376. Formal observations collected:0. Prepared32 deterministic positive-alpha model inputs for evaluation-only truth; all local model bytes and registry SHA256s verified without numerical array loading.

|task|alpha|algorithm|seconds at rungs1/64,1/16,1/4,1|process peak RSS KiB|equivalence|
|---:|---:|---|---|---:|---|
{chr(10).join(rows)}

Slurm elapsed times397/388/393/388s, all billing=1. Completed Slurm elapsed cost **{elapsed_su:.6f} SU**; requested **1/50 SU**. AMS has no matching own-X9 row at {accounting['checked_utc']}, so settlement is pending; do not call its missing entry zero or add it to Slurm. Maximum Slurm/process RSS {peak:.0f} KiB ({peak/1024:.3f} MiB), memory headroom {headroom:.2%} of2GiB, exceeding20%.

Measured maxima: full NPG {predicted['n24-full-NPG']:.3f}s, full PI {predicted['n24-full-PI']:.3f}s; the conservative combined low-three body is {predicted['n24-low-three']:.3f}s. Frozen wall guards1.20*body+30 are {1.2*predicted['n24-full-NPG']+30:.3f}s / {1.2*predicted['n24-full-PI']+30:.3f}s / {1.2*predicted['n24-low-three']+30:.3f}s, within420/420/480s. PASS. No limit or scientific grid change needed.

FORMAL plan:12 sequential arrays ×32 tasks,1CPU/2GiB, per alpha8min(low-three both algorithms),7min(full NPG),7min(full PI); global concurrency<=8, afterok order, automatic retries0. Four new alphas.05/.1/.2/.4; alpha0 reused in full. Requested **{formal_su:.6f} SU**, plus pilot1 and REPORT reserve2 = **{1+formal_su+2:.6f}/50 SU**. Real actor-body estimate at8cores {plan['estimated_formal_body_hours_at_8cores']:.3f}h; requested allocation envelope {formal_su/8:.3f}h, plus queue/review/report time. Source/config hashes and each32-model registry are in the frozen formal config/plan. No formal submission yet.

Formal config SHA256 `{sha(formal_path)}`. All5 scientific hashes equal the PROTOCOL freeze. Source checks,32 model hashes and70 transferred member hashes PASS. Pilot model solves were input/evaluation preparation, with no formal sampling, retuning or performance selection. Exact-rank redundant-cost shares remain baseline-only; positive-alpha fields are N/A. The registered empirical scan is outside numerically certified Theorem3 conditions, not a theorem verification.

Files: `experiments/x9-20261106/` PILOT_REPORT_v1.md, PILOT_ACCOUNTING_v1.json, PILOT_DELIVERY_VERIFIED_v1.json, pilot-delivery-v1/, and prepared-formal-v1/formal-config.json/formal-plan.json. No old results/releases/paper tex changed. Await your explicit **PILOT ACCEPTED** before FORMAL.
'''
    report_path = HERE/'PILOT_REPORT_v1.md'
    with report_path.open('x', encoding='utf-8') as stream:
        stream.write(report)
    files = [report_path, formal_path, HERE/'prepared-formal-v1/formal-plan.json',
             HERE/'PILOT_ACCOUNTING_v1.json', HERE/'PILOT_DELIVERY_VERIFIED_v1.json', progress_path]
    new(HERE/'PILOT_MANIFEST_v1.json', dict(status=plan['status'],
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        review_sha256=EXPECTED_REVIEW,
        files={str(p.relative_to(HERE)): sha(p) for p in files},
        pilot_archive_sha256=delivery['archive_sha256'], scientific_sources=cfg['scientific_sources']))
    body = report.split('\n', 1)[1].lstrip().replace('\n## ', '\n### ')
    section = ('\n\n## X9 PILOT\n\n'+body.rstrip()+'\n\nPILOT manifest SHA256 `'
               +sha(HERE/'PILOT_MANIFEST_v1.json')+'`.\n\nSTATUS: PILOT DONE X9\n').encode()
    assert sha(task) == EXPECTED_REVIEW and reply.read_bytes() == prior
    with reply.open('ab') as stream:
        stream.write(section)
    assert reply.read_bytes() == prior+section
    new(HERE/'PILOT_APPEND_RECEIPT_v1.json', dict(
        prior_reply_bytes=len(prior), prior_reply_sha256=hashlib.sha256(prior).hexdigest(),
        appended_bytes=len(section), appended_sha256=hashlib.sha256(section).hexdigest(),
        prior_prefix_preserved=True, review_sha256=EXPECTED_REVIEW))
    print(json.dumps(plan))


if __name__ == '__main__':
    main()
