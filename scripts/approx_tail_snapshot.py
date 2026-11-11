"""Freeze complete budget tiers and audit/plot them on a Grace compute node."""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path
from dense_scaling import require_compute, atomic_json


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(manifest, production, output):
    manifest, production, output = map(Path, (manifest, production, output))
    assert not output.exists(), 'Snapshot output must be new'
    cfg = json.loads(manifest.read_text())
    expected = len(cfg['tasks'])
    counts = {profile: len(list((production / profile / 'raw').glob('task-*.json')))
              for profile in cfg['profiles']}
    selected = [profile for profile, count in counts.items() if count == expected]
    assert 'ce' in selected and any(p.startswith('npg-') for p in selected)
    output.mkdir(parents=True)
    inputs = {}
    for profile in selected:
        for task in cfg['tasks']:
            relative = Path(profile) / 'raw' / f"task-{task['id']:03d}.json"
            source = production / relative
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            inputs[str(relative)] = sha(destination)
    shutil.copytree(production / 'reference', output / 'reference')
    shutil.copyfile(production / 'verification.json', output / 'verification.json')
    source_dir = output / 'source'
    source_dir.mkdir()
    original = manifest.parent.parent / 'scripts' / 'approx_tail_report.py'
    script = original.read_text()
    needle = "cfg=json.loads(manifest.read_text()); out=root/'report'; out.mkdir(exist_ok=True)"
    assert script.count(needle) == 1
    replacement = needle + '\n    cfg[\'profiles\']={k:v for k,v in cfg[\'profiles\'].items() if k in ' + repr(selected) + '}'
    script = script.replace(needle, replacement)
    # Complete refers only to the declared frozen subset, never all planned tiers.
    script = script.replace("dict(status='complete',complete_tasks=", "dict(status='snapshot_complete',complete_tasks=")
    snapshot_script = source_dir / 'snapshot_report.py'
    snapshot_script.write_text(script)
    shutil.copyfile(manifest, source_dir / manifest.name)
    shutil.copyfile(__file__, source_dir / Path(__file__).name)
    atomic_json(output / 'snapshot_scope.json', dict(status='frozen_subset',
        original_release=manifest.parent.parent.name, production=str(production),
        completed_configurations_at_snapshot=sum(counts.values()), planned_configurations=expected*len(cfg['profiles']),
        coverage_by_profile=counts, selected_complete_profiles=selected, excluded_incomplete_profiles=[
            p for p in cfg['profiles'] if p not in selected], slurm_job_id=os.environ['SLURM_JOB_ID'],
        interpretation='Interim snapshot of complete tiers. Minimum tested precision budgets and censoring apply '
                       'only to this subset; remaining higher tiers can change sustained-attainment conclusions.',
        original_report_source_sha256=sha(original), snapshot_report_source_sha256=sha(snapshot_script),
        snapshot_runner_source_sha256=sha(__file__), manifest_sha256=sha(manifest), input_sha256=inputs))
    spec = importlib.util.spec_from_file_location('frozen_snapshot_report', snapshot_script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(manifest, output)
    summary = json.loads((output / 'report' / 'summary.json').read_text())
    assert summary['status'] == 'snapshot_complete'
    assert json.loads((output / 'report' / 'numerical_audit.json').read_text())['status'] == 'PASS'
    atomic_json(output / 'snapshot_completion.json', dict(status='PASS', selected_complete_profiles=selected,
        method_groups=summary['sampled_method_groups'], stable_complete_groups=summary['stable_method_groups'],
        original_production_unchanged=True, original_report_and_models_unchanged=True))


if __name__ == '__main__':
    require_compute()
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--production', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    main(args.manifest, args.production, args.output)
