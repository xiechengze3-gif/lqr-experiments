"""Freeze X10a only; X10b remains separately stopped for a resource decision."""
import ast
import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
EXPECTED_REVIEW = '97173f645c72d54497aa5594e7d31bb4e32a26935b81e0adada4b9897b1b474e'
PAPER_DATA = Path('C:/Users/24375/Projects/project2_l4dc/figs/data')


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def new(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(payload)


def main():
    review = (CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert sha(review) == EXPECTED_REVIEW
    assert b'## X10 GO (23:00 CDT 11/05)' in review
    prior = (CHANNEL/'CODEX_REPLY.md').read_bytes()
    assert b'## X10a PROTOCOL' not in prior
    names = [str(p.relative_to(HERE)).replace('\\', '/') for p in sorted((HERE/'ce-src').glob('*.py'))]
    assert len(names) == 6
    for name in names:
        ast.parse((HERE/name).read_text(encoding='utf-8'), filename=name)
    baseline = {}
    for name in ['X8_sample_cost.csv', 'X6a_sample_cost_derived.csv', 'X1_normalized_statistics.csv']:
        payload = (PAPER_DATA/name).read_bytes()
        new(HERE/'ce-baseline'/name, payload)
        baseline[name] = dict(original_path=str(PAPER_DATA/name), bytes=len(payload), sha256=sha(payload))
    for name in ['PROTOCOL.md', 'PROTOCOL_AMENDMENT.md', 'analysis/analyze_x8.py']:
        source = HERE.parent/'x8-local-20261104'/name
        new(HERE/'ce-baseline/x8-source-docs'/name, source.read_bytes())
    sources = {name: sha((HERE/name).read_bytes()) for name in names}
    for p in (HERE/'ce-baseline').rglob('*'):
        if p.is_file():
            sources[p.relative_to(HERE).as_posix()] = sha(p.read_bytes())
    cases = [dict(family='exact', config=f'r{r}', rank=r) for r in [3, 6, 12, 24]]
    cases += [dict(family='geometric', config=f'rho{rho}', rho=rho) for rho in [.4, .6, .75, .85]]
    config = dict(experiment='X10a', status='PROTOCOL_FROZEN',
                  execution='LOCAL_AUTHOR_APPROVED_X10a', original_review_sha256=EXPECTED_REVIEW,
                  sources=sources, baseline_csvs=baseline, x8_cases=cases,
                  x8_N=[2**p for p in range(9, 19)], x8_systems=list(range(8)), x8_seeds=list(range(4)),
                  dimension_n=[16, 20, 30, 42, 60, 84, 96],
                  dimension_N=[2048, 8192, 32768, 131072, 524288],
                  dimension_N_large=[2048, 8192, 32768, 131072, 524288, 1048576],
                  dimension_systems=list(range(301, 309)), dimension_seeds=list(range(1601, 1605)),
                  redundant_inputs=[1, 3, 5, 6, 8, 9], redundancy_N=[4096, 8192],
                  redundancy_systems=list(range(101, 109)), redundancy_seeds=list(range(1001, 1005)),
                  ce_burn=512, nu=1, local_memory_ceiling_bytes=2*1024**3,
                  pilot_systems=[9901, 9902, 9903], pilot_seeds=[7701, 7702, 7703],
                  local_workers=1, threads=1, Grace_requested_SU=0,
                  new_physical_paths=672, new_formal_primitive_transitions=236797952,
                  required_pilot_status='LOCAL_RESOURCE_EQUIVALENCE_PASS',
                  automatic_retries=0, X10b_status='RESOURCE_REVIEW_REQUIRED_NO_JOBS')
    new(HERE/'ce-config-protocol-v1.json', (json.dumps(config, indent=2)+'\n').encode())
    table = '\n'.join(f'|{name}|{digest}|' for name, digest in sources.items() if name.startswith('ce-src/'))
    protocol = f'''# X10a PROTOCOL v1 — CE densification, local route

X10 GO authorizes local CE, new configurations only. Explicit local provenance, no Slurm job id, no fabricated compute-node status. One worker, one BLAS/OpenMP/Numba thread. Grace spend0SU for all X10a stages. X10b is independently stopped for its reported resource issue; no X10b approval is inferred here.

Frozen source functions and streams are those of each original panel: author-local X8 run_x8.py unchanged; exact9915fc... frozen engine for X1 and S CE; model and ce_prefixes functions extracted byte-for-byte from the *frozen* F587bd... estimator (not the later904ffaa... working copy). Portable imports omit the Unix-only resource module. The pilot reference preserves every ce_run numerical statement, replacing only its Slurm provenance read with explicit local provenance. Truth is used only in simulator/evaluation, never to choose learner order/parameters. Paired arms share one OLS fit; no new whitening/ridge/critic. Pulse actors are not part of X10a.

Panel(a):n=m48,new exactr3/6/12/24 and geometricrho.4/.6/.75/.85. Original X8 systems0..7,seeds0..3, A/B/noise namespaces unchanged; all Gaussian pulse arrays are drawn before all process-noise arrays, and the original scalar-time OLS accumulation is preserved. All orders1..47+dense at each512..262144 prefix (powers2). Model independent A/B as original; Q=R=W=I,K0zero,nu1,burn512. Absolute targets.01/.005 and the existing documented X8 absolute-target analysis amendment. Effective ranks at.01=3/5/10/19 and.005=3/6/11/21, spectrum-only finite48-dimensional sums. No outcome-dependent order selection.

Panel(b):same frozen S CE model/collector/learner, newn16/20/30/42/60/84/96,rank2,K0zero,p0bound1.5625, systems301..308,seeds1601..1604. Old N grid2048/8192/32768/131072/524288. Forn>=60 append1048576 (the next power after the old maximum), frozen before any run. Original rng(10,n,m,system,seed),512burn,nestedcontinuous trajectory/shared OLS. Dense and rank2 from the same fit. Absolute target.01, original log-log first-downcross arithmetic; regressionN and burn-inclusiveM=N+512 both in raw data.

Panel(c):original unstable independent-A/B X1 construction,n12,r2,nullscale.25,newm-r1/3/5/6/8/9 (m3/5/7/8/10/11),systems101..108,seeds1001..1004,N4096/8192,burn512. CE dense/truncated only. Per-output normalizeN*D/vstar, vstar=||Pstar(A-BKstar)||F² from matching model, then take full32 median/IQR exactly as originalrefine_ce. Failed outputs remain+inf. No old configurations are rerun for CE.

Complete formal counts:256 X8 trajectories,224 S-dimension trajectories,192 X1 trajectories =672 physical paths,236797952 transitions including burn once per path (not a sum over shared arms/prefixes).122880 X8outputs,2432 dimensionoutputs,768 redundant-inputoutputs. Fixed model/seed/config lists in ce-config-protocol-v1.json.

Pilot, before formal and with no performance-based selection: three disjoint inputs only. (1) X8 n48rho.85,sys9901seed7701,all480 outputs of the unchanged original run function/source identity and full count check; (2) S n96,sys9902seed7702,full largest-prefix grid; (3) X1 n12m11,null.25,sys9903seed7703,N4096/8192. Cases2/3 compare complete prefix theta, gain arrays, assessed values and final RNG state/primitive counts bitwise against the originalce_run numerical reference, and count both physical validation trajectories. Time and peak working set only are printed; no stability/gap accuracy selection or retuning. Require source identity, bitwise comparisons/counts and <=2GiB process peak. Otherwise stop/report, no automatic retry. No formal observations collected during pilot.

Before any numerical import/run, launcher checks actual E-drive output/cache/temp paths, free disk and memory; sets TMPDIR/TEMP/TMP to E:/ChatGPT/Temp/LQR_X10a_20261106, XDG/Numba/Matplotlib caches to E:/ChatGPT/Cache/LQR_X10a_20261106, source/outputhereonE; existing E:/anaconda/python.exe, no installations. Threadpoolctl must confirm one thread per loaded numerical library. Small stdlib source/count checks have run; no numerical pilot/formal/data re-analysis has run at protocol publication. Pilot and formal use explicit LOCAL_AUTHOR_APPROVED_X10a provenance. Store complete per-prefix fits/policies/model certificates and immutable path receipts. New output directories only; no overwrite or automatic restart of partial paths.

After all fixed pilot checks PASS, publish PILOT and a time/memory estimate, reread the review log, then FORMAL automatically as X10 GO directs (no extra approval round). Resource failure stops/report. REPORT after complete source/count/hash coverage: full32 failure-inclusive medians, original X8 2000 system bootstrap/seed0 and crossing/censoring, S-dimension median-curve crossing.01, and original X1 normalized median/IQR. Export new-only main CSVs with exactly the original schemas, plus merged copies made by appending new rows to the original baseline bytes. Verify each entire baseline prefix byte-identical. Supplement censor flags/first-grid bounds, all failures, new raw records, fit/model hashes and local provenance. Old bootstrap or old records are never recomputed. Nonfinite/unidentified results remain visible. No smoothing/extrapolation or new epsilon/probability/theorem claim. This is descriptive densification; paper tex/figs code is read-only.

Config SHA256 `{sha((HERE/'ce-config-protocol-v1.json').read_bytes())}`.

|source|SHA256|
|---|---|
{table}

X10a requested/actual Grace spend0/0SU. X10b requested/actual0/0SU remains stopped separately. X9 requested47.9333333SU plus2reportreserve<=50 and its accepted formal chain continues.
'''
    new(HERE/'CE_PROTOCOL_v1.md', protocol.encode())
    manifest = dict(status='X10a_PROTOCOL_FROZEN_NO_NUMERICS_YET',
                    created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    review_sha256=EXPECTED_REVIEW, config_sha256=sha((HERE/'ce-config-protocol-v1.json').read_bytes()),
                    protocol_sha256=sha(protocol.encode()), sources=sources,
                    Grace_requested_SU=0, Grace_actual_SU=0, new_jobs=0,
                    source_extraction_proof_sha256=sha((HERE/'CE_SOURCE_PREPARATION_v1.json').read_bytes()))
    new(HERE/'CE_PROTOCOL_MANIFEST_v1.json', (json.dumps(manifest, indent=2)+'\n').encode())
    section = ('\n\n## X10a PROTOCOL\n\n'+protocol.split('\n', 1)[1].lstrip().replace('\n## ', '\n### ')
               +'\nFiles: `experiments/x10-20261106/CE_PROTOCOL_v1.md`, `ce-config-protocol-v1.json`, '
               '`ce-src/`, `ce-baseline/`, `CE_PROTOCOL_MANIFEST_v1.json`. This completes the CE subprotocol only; '
               'X10b resource review is separate.\n\nSTATUS: PROTOCOL DONE X10a\n').encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes() == review
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes() == prior
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:
        stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes() == prior+section
    new(HERE/'CE_PROTOCOL_APPEND_RECEIPT_v1.json', (json.dumps(dict(
        prior_reply_bytes=len(prior), appended_bytes=len(section), prior_prefix_preserved=True,
        review_sha256=EXPECTED_REVIEW), indent=2)+'\n').encode())
    print(json.dumps({k: v for k, v in manifest.items() if k != 'sources'}))


if __name__ == '__main__':
    main()
