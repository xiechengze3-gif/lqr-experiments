"""Saved-data X12 report using original analyzer and cross functions verbatim."""
import argparse
import hashlib
import json
import os
import sys
import tarfile
from pathlib import Path

from recovery_archive_reader_v5 import ArchiveReader, NumpyReadProxy, RawPath
from recovery_driver_v5 import ORIGINAL, ORIGINAL_CONFIG_SHA256, SOURCE_FILES, node_storage
from reconstruct_reuse_for_report_v5 import EVIDENCE, EVIDENCE_SHA, reproduce
from virtual_task_store_v2 import file_sha


def bundled(name):
    return __loader__.get_data(str(Path(__file__).with_name(name))) if '/' not in name else \
        __loader__.get_data(str(Path(__file__).parent / name))


def exclusive_json(path, d):
    with path.open('x', encoding='utf-8') as f:
        json.dump(d, f, indent=2)


def main(a):
    assert os.environ.get('SLURM_JOB_ID') and a.root.is_dir()
    assert not (a.root / 'recovery-report-v5.tar.gz').exists() and not (a.root / 'recovery-report-DONE.json').exists()
    node = node_storage(a.root)
    work = Path(os.environ['TMPDIR']).resolve() / 'x12-saved-report-v5'
    work.mkdir(mode=0o700)
    config = json.loads(a.config.read_bytes())
    cs = file_sha(a.config)
    assert file_sha(ORIGINAL / 'formal-config.json') == ORIGINAL_CONFIG_SHA256
    for n, h in SOURCE_FILES.items():
        assert file_sha(ORIGINAL / n) == h
    # The ZIP includes the literal frozen analyzer, paper cross, and renderer.
    sys.path.append(str(ORIGINAL))
    import analyze_actor as analysis
    import frozen_engine as e
    import paper_cross as cross
    import report_products_v1 as products
    import report_render_v3 as render
    e.require_compute()

    def sha(path):
        if isinstance(path, RawPath):
            return hashlib.sha256(path.read_bytes()).hexdigest()
        p = Path(path)
        bundle = Path(__file__).parent
        if p.is_relative_to(bundle):
            return hashlib.sha256(bundled(p.relative_to(bundle).as_posix())).hexdigest()
        return file_sha(p)

    assert sha(analysis.__file__) == config['scientific_sources']['analyze_actor.py']
    assert sha(cross.__file__) == 'd07e548f861e7edf4191c9735015553706d012dfca2077adc7b5d212ea9e5a8e'
    reused = json.loads(bundled('REUSED_COMPLETE_PATHS_v2.json'))
    assert reused['old_failed_evidence_archive_sha256'] == EVIDENCE_SHA
    assert reused['archive_bytes'] + 512 * 1024**2 < .8 * node['free_bytes']
    old_tar = work / 'reused-complete-paths-v2.tar'
    old_proof = reproduce(EVIDENCE, old_tar, reused)
    plan = json.loads(bundled('recovery-membership.json'))
    reader = ArchiveReader(a.root, plan, reused, cs, old_tar)
    original_sha, original_np = e.sha, analysis.np
    report = work / 'report-v1'
    try:
        coverage = reader.verify_all()
        e.sha = sha
        analysis.np = NumpyReadProxy(original_np)
        analysis.BASE = work
        analysis.inspect(a.config, reader.raw, report / 'diagnostics-n60', 60)
        analysis.summarize(a.config, report, report / 'new-n60')
        products.B, products.R = work, work
        baseline = work / 'baseline'
        baseline.mkdir()
        for n in ('summary.csv', 'transitions_saved_derived.csv', 'failures.csv', 'failure_counts_by_cell.csv', 'MANIFEST_v1.json'):
            with (baseline / n).open('xb') as f:
                f.write(bundled('baseline/' + n))
        products.main(a.config)
        render.BASE = work
        render.main(a.config)
        exclusive_json(report / 'ARCHIVE_COVERAGE_v5.json', coverage)
        exclusive_json(report / 'RECOVERY_PROVENANCE_v5.json', dict(
            original_config_sha256=ORIGINAL_CONFIG_SHA256, source_bytes_verified=SOURCE_FILES,
            old_reference=old_proof, node_storage=node, config_sha256=cs, new_training_transitions=0,
            report_job=os.environ['SLURM_JOB_ID'], no_mid_path_resume=True,
            accepted_transitions=coverage['accepted_transitions'], no_old_results_edited=True))
        supplement = report / 'RECOVERY_NOTE.md'
        with supplement.open('x', encoding='utf-8') as f:
            f.write('# X12 recovery provenance\n\n'
                    'The initial formal attempt stopped on the storage quota. That infrastructure '
                    'failure is separate from policy instability. The complete and SHA-verified 296 '
                    'paired paths were reused, and the other 280 paired paths restarted from K0 '
                    'with the same registered seeds and schedules. No path resumed mid-run. '
                    'The logical training count is 193,644,738,560 primitive transitions: '
                    '9,476,201,216 from verified old paths and 184,168,537,344 from the recovery. '
                    'All Slurm costs from the failed attempt remain in the accounting. '
                    'The storage-only pilots generated zero training observations.\n')
    finally:
        e.sha, analysis.np = original_sha, original_np
        reader.close()
    archive = a.root / 'recovery-report-v5.tar.gz'
    files = sorted(p for p in report.rglob('*') if p.is_file())
    entries = [dict(path=p.relative_to(report).as_posix(), bytes=p.stat().st_size, sha256=file_sha(p)) for p in files]
    assert sum(m['bytes'] for m in entries) < 256 * 1024**2
    with tarfile.open(archive, 'x:gz', compresslevel=1) as tf:
        for path, meta in zip(files, entries):
            tf.add(path, arcname=meta['path'], recursive=False)
    receipt = dict(status='X12_RECOVERY_REPORT_ARCHIVE_COMPLETE', archive_sha256=file_sha(archive),
                   archive_bytes=archive.stat().st_size, files=entries, config_sha256=cs,
                   job=os.environ['SLURM_JOB_ID'], new_training_transitions=0)
    exclusive_json(a.root / 'recovery-report-DONE.json', receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k != 'files'}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--root', type=Path, required=True)
    main(p.parse_args())
