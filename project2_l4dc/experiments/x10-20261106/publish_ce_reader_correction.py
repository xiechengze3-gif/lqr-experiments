"""Disclose the saved-record Windows path fix; no experimental retry or data change."""
import argparse
import ast
import builtins
import hashlib
import json
import symtable
from pathlib import Path

HERE=Path(__file__).resolve().parent
CHANNEL=HERE.parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-review-sha256',required=True);args=p.parse_args()
    review=(CHANNEL/'CLAUDE_TASK.md').read_bytes();assert hashlib.sha256(review).hexdigest()==args.expected_review_sha256
    proof=json.loads((HERE/'CE_REPORT_READER_CORRECTION_v3.json').read_text(encoding='utf-8'))
    assert proof['status']=='PASS_METADATA_READER_FIX_ONLY' and not proof['failed_attempt_statistics_started']
    for name,digest in proof['files'].items():assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==digest
    for name in ['ce-report-src-v3/analyze_ce.py','render_ce_report_v3.py','finalize_ce_report_v3.py']:
        code=(HERE/name).read_text(encoding='utf-8');ast.parse(code);table=symtable.symtable(code,name,'exec')
        known=set(table.get_identifiers())|set(dir(builtins))|{'__file__','__name__'};missing=set()
        def walk(t):
            for s in t.get_symbols():
                if s.is_global() and s.is_referenced() and s.get_name() not in known:missing.add(s.get_name())
            for child in t.get_children():walk(child)
        walk(table);assert not missing,(name,missing)
    receipt=HERE/'CE_READER_CORRECTION_APPEND_RECEIPT_v3.json';assert not receipt.exists()
    prior=(CHANNEL/'CODEX_REPLY.md').read_bytes()
    section=f'''

## X10a REPORT reader correction

Formal coverage/source/count/model/1600fit-artifact audit PASSED and FORMAL DONE is posted. The first saved-record reader then stopped BEFORE any statistics/bootstrap output: formal local paths are Windows strings (`x8\\r3\\s0-t0`), but its dispatch tested literal forward-slash prefixes. Thus the reader incorrectly classified all126080records as redundancy, while independent nativePath coverage gives the exactregistered122880X8/2432dimension/768redundancycounts. This is a report input-dispatch portability bug, not a failed simulation, changed result or statistical mismatch. Empty ce-report-v2 and old frozen source retained.

Prepared a new saved-data-only reader `ce-report-src-v3/analyze_ce.py`: replace only the namespace test with `Path(ref['path']).parts[0]`, and use new output ce-report-v3. No assertion removed. Entire main reverses exactly to original after those two metadata/output substitutions; `write_csv`, `q`, `cost`, `merge_bytes` are literal source-identical. Targets, median/IQR, bootstrap draws, censor arithmetic, seeds and allformaldata unchanged. Original analyzer SHA256 `{proof['old_analysis_sha256']}`; newreader SHA256 `{proof['new_analysis_sha256']}`; source/metadata proof `CE_REPORT_READER_CORRECTION_v3.json`. All3newreport/presentation/delivery scripts AST/globaldependencies PASS. Old ce-src-v2/config hashes remain byte-identical. New launch control imports the original frozen numerical modules via explicitEdrivePYTHONPATH.

Continuing the already-authorized REPORT into ce-report-v3, with separate versioned renderer/finalizer. Zero new trajectories, no bootstrap/summary had completed in the failed dispatch, no scientific parameter/method choice, no experimental job resubmitted,0GraceSU. This fixes only necessary reader compatibility while keeping the registered analysis. Canonical CSVs will be published only after successful statistics/byte-preservation/imageQA. X10b corrected pilot remains STOPPEDpendingyourauthorization; not retried.

Running spend: X10a0GraceSU. CompletedX9formal28.844722SU+pilot.435SU and failedX10bpilot.015833SU =>29.295556SU completed, plus the separatelyrunning X9report job20415797 (requestedupper2SU). No AMS/Slurm doublecounting; failed/canceledBrequestedupper4.166667 is not actualspent. Alloldrecords/releases/paperunchanged.

STATUS: REPORT RUNNING X10a
'''.encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes()==review and (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior+section
    with receipt.open('x') as stream:json.dump(dict(prior_bytes=len(prior),appended_bytes=len(section),prior_preserved=True,review_sha256=args.expected_review_sha256),stream,indent=2)
    print(json.dumps(dict(status='REPORT_READER_CORRECTION_DISCLOSED',new_training_transitions=0,new_jobs=0,Grace_SU=0)))


if __name__=='__main__':main()
