"""Verify a relaxed-tolerance study; reuse only tolerance-independent jobs."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--old-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--old-output', type=Path, required=True)
    args = parser.parse_args()
    cfg = json.loads(args.manifest.read_text())
    previous_cfg = json.loads(args.old_manifest.read_text())
    unchanged = dict(cfg)
    unchanged['solver_rtol'] = previous_cfg['solver_rtol']
    assert unchanged == previous_cfg, 'Reuse is allowed only for a tolerance-only change'
    assert cfg['solver_rtol'] > previous_cfg['solver_rtol']
    runner = Path(__file__).parent / 'fixed_value_run.py'
    args.output.mkdir(parents=True, exist_ok=True)
    status_path = args.output / 'bootstrap_status.json'
    save(status_path, dict(status='RUNNING', phase='verification', solver_rtol=cfg['solver_rtol']))
    from fixed_value_run import identity
    proof_path = args.output / 'verification.json'
    proof = json.loads(proof_path.read_text()) if proof_path.exists() else {}
    if proof.get('status') != 'PASS' or proof.get('identity') != identity(args.manifest):
        with (args.output / 'verify.log').open('ab') as log:
            subprocess.run([sys.executable, '-B', str(runner), 'verify', '--manifest', str(args.manifest),
                            '--output', str(args.output)], stdout=log, stderr=subprocess.STDOUT, check=True)
    ident = json.loads((args.output / 'verification.json').read_text())['identity']
    old_ident = json.loads((args.old_output / 'verification.json').read_text())['identity']
    assert ident['sources'] == old_ident['sources']
    provenance = dict(original_output=str(args.old_output), original_identity=old_ident,
                      justification='Only LSTD solver_rtol changed; CE, Direct PI, NPG and population reference do not read it.')
    reused = []
    for algorithm in ('CE', 'DIRECT_PI', 'NPG'):
        for task in cfg['tasks']:
            filename = f"task-{task['id']:03d}.json"
            source = args.old_output / algorithm / 'raw' / filename
            if source.exists():
                data = json.loads(source.read_text())
                assert data['identity'] == old_ident and data['task'] == task
                data['identity'] = ident
                data['reuse_provenance'] = dict(provenance, original_file=str(source), original_sha256=digest(source))
                save(args.output / algorithm / 'raw' / filename, data)
                reused.append(dict(algorithm=algorithm, task=task['id'], kind='complete'))
            else:
                import numpy as np
                source = args.old_output / algorithm / 'checkpoints' / filename.replace('.json', '.npz')
                if not source.exists():
                    continue
                with np.load(source, allow_pickle=False) as archive:
                    assert json.loads(str(archive['identity'])) == old_ident
                    values = {key: archive[key].copy() for key in archive.files}
                values['identity'] = np.array(json.dumps(ident, sort_keys=True))
                target = args.output / algorithm / 'checkpoints' / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('wb') as stream:
                    np.savez(stream, **values)
                save(target.with_suffix('.reuse.json'), dict(provenance, original_file=str(source), original_sha256=digest(source)))
                reused.append(dict(algorithm=algorithm, task=task['id'], kind='checkpoint'))
    source = args.old_output / 'population_reference.json'
    reference = json.loads(source.read_text())
    assert reference['identity'] == old_ident and reference['status'] == 'COMPLETE'
    reference['identity'] = ident
    reference['reuse_provenance'] = dict(provenance, original_sha256=digest(source))
    save(args.output / source.name, reference)
    save(args.output / 'reuse_audit.json', dict(identity=ident, changed_only='solver_rtol',
        old_tolerance=previous_cfg['solver_rtol'], new_tolerance=cfg['solver_rtol'], reused=reused,
        LSTD_learning_results_reused=False, population_reference_reused=True))
    save(status_path, dict(status='RUNNING', phase='failed_batch_audit', solver_rtol=cfg['solver_rtol'], reused=reused))
    # Replay this single historical batch before the new complete learning runs.
    with (args.output / 'failed_batch_audit.log').open('ab') as log:
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).parent / 'relaxed_lstd_failed_batch.py'),
            '--old-manifest', str(args.old_manifest), '--old-output', str(args.old_output),
            '--output', str(args.output / 'diagnostics' / 'dense-task000-stage7.json'),
            '--rtol', str(cfg['solver_rtol'])], stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        save(status_path, dict(status='FAILED_AUDIT', exit_code=result.returncode, reused=reused))
        raise SystemExit(result.returncode)
    save(status_path, dict(status='RUNNING', phase='learning', solver_rtol=cfg['solver_rtol'], reused=reused))
    result = subprocess.run([sys.executable, '-B', str(Path(__file__).parent / 'fixed_value_pipeline.py'),
        '--manifest', str(args.manifest), '--output', str(args.output)])
    save(status_path, dict(status='COMPLETE' if result.returncode == 0 else 'FAILED_PIPELINE',
                          exit_code=result.returncode, reused=reused))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
