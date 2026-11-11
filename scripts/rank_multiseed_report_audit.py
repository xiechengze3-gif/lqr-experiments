"""Synthetic reporting fixture: test failure/censor inclusion, never experimental data."""
import argparse
import json
from pathlib import Path
from dense_scaling import require_compute, atomic_json, evaluate
from rank_multiseed_run import sha
import rank_multiseed_report as reporting


def main(manifest, output):
    manifest=Path(manifest)
    cfg=json.loads(manifest.read_text())
    fixture=Path(output)/'REPORT_SCHEMA_FIXTURE_NOT_EXPERIMENT'
    fixture.mkdir(parents=True,exist_ok=True)
    release=manifest.parent.parent
    expected=dict(manifest_sha256=sha(manifest),source_sha256=sha(release/'scripts/rank_multiseed_run.py'),
        system_sha256=sha(release/'scripts/approx_tail_system.py'),lstd_sha256=sha(release/'scripts/full_lstd.py'),
        collector_sha256=sha(release/'scripts/npg_batched_collector.py'),engine_sha256=sha(evaluate.__code__.co_filename))
    atomic_json(fixture/'verification.json',dict(status='PASS',engine_sha256=expected['engine_sha256'],synthetic_fixture=True))
    atomic_json(fixture/'resume-audit/resume_audit.json',dict(status='PASS',synthetic_fixture=True))
    for task in cfg['tasks']:
        records=[]
        for count in cfg['profiles']['ce']['budgets']:
            for method in ('raw','truncated'):
                stable=task['system_seed']!=9
                factor=task['n'] if method=='raw' else task['r']
                gap=factor*task['n']*(1.+.1*task['system_seed'])/(count+512)
                records.append(dict(method=method,N=count,transitions=count+512,stable=stable,
                                    gap=gap if stable else None))
        matrices={key:f"fixture-{key}-n{task['n']}-seed{task['system_seed']}" for key in ('A','Q','R','K0')}
        matrices['B']=f"fixture-B-{task['id']}"
        atomic_json(fixture/'ce/raw'/f"task-{task['id']:03d}.json",dict(task=task,records=records,
            diagnostics=dict(matrix_sha256=matrices,tail_energy=0. if task['tail_mode']=='exact' else .0009),**expected))
    reporting.main(manifest,fixture,['CE'])
    summary=json.loads((fixture/'report-ce/summary.json').read_text())
    def cell(fraction):
        return next(t for t in summary['thresholds'] if t['n']==100 and t['r']==4 and
            t['tail_mode']=='exact' and t['method']=='truncated' and t['epsilon']==.03 and t['success_fraction']==fraction)
    threshold=cell(.8)
    assert threshold['budget']==33280 and threshold['required_systems']==8
    assert threshold['bootstrap_upper_censored'] and threshold['bootstrap95_upper'] is None
    assert cell(1.)['status']=='right_censored' and cell(1.)['budget'] is None
    coverage=json.loads((fixture/'report-ce/coverage.json').read_text())
    assert coverage['missing']==[]
    task=cfg['tasks'][0]
    missing=fixture/'ce/raw'/f"task-{task['id']:03d}.json"
    held=missing.with_suffix('.held')
    missing.rename(held)
    rejected=False
    try:
        reporting.main(manifest,fixture,['CE'])
    except AssertionError:
        rejected=True
    finally:
        held.rename(missing)
    assert rejected, 'Missing infrastructure outputs were silently treated as failed systems'
    atomic_json(Path(output)/'report_schema_audit.json',dict(status='PASS',synthetic_fixture=True,
        empirical_8_of_10_budget_correct=True,failed_system_not_dropped=True,
        bootstrap_upper_censor_preserved=True,all_systems_threshold_censored=True,missing_output_rejected=True,
        source_sha256=sha(__file__)))
    print(json.dumps(dict(report_schema_audit='PASS',synthetic_fixture=True)),flush=True)


if __name__=='__main__':
    require_compute()
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    main(args.manifest,args.output)
