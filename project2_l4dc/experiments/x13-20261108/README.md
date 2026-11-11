# X13 (2026-11-08): CE redundant cost, null part 0, m-r in {1,3,5,6,8,9}

Purpose: fill the cells of App. H.6 / Table 8 (tab:redundant) that were never run. X10a densified the
redundant-cost panel only with null part 0.25 (CE_PROTOCOL_v1.md, panel (c)); the variant without the
component of K0 along ker B (null part 0) had only m-r in {2,4,7,10} from the original X1 run.

Configuration (fixed before running, no outcome-dependent choice): original unstable independent-A/B
construction `frozen_engine.plant(12, m, 2, system, null_scale=0.)`, m = 2 + (m-r), systems 101..108,
seeds 1001..1004, N in {4096, 8192}, burn 512, nu 1, CE dense (rank min(n,m)) and truncated (rank 2) from
one shared OLS fit, stream `rng(10, n, m, system, seed)`. Statistic: N * D / v_star per output,
v_star = ||P*(A - B K*)||_F^2, +inf for a non-stabilizing output; median and quartiles over the 32
outputs with analyze_ce.q. This is the numerical path of X10a ce_driver.run_shared_ce / analyze_ce.py.

Sources: `src/frozen_engine.py` (sha256 9915fc38...a989) and `src/s_ce_original.py` (3e9aedc9...1c27),
byte-identical to x10-20261106/ce-src-v2 and to the hashes in ce-config-protocol-v2.json.
`run_null0.py` is the driver. numba is not installable in the environment used (PyPI unreachable), so
`shim/numba/__init__.py` makes `njit` the identity; the frozen engine file is not modified, only its
compiled loops run as plain Python.

Environment: Claude cloud workspace (Linux, Python 3.13, numpy 2.5.3, scipy 1.18.1), one BLAS thread
(OPENBLAS/MKL/OMP_NUM_THREADS=1). Run on 2026-11-08 at the author's request.

Validation (stage `validate`, run before `formal`): recomputes the 20 published cells null 0 with
m-r in {2,4,7,10} (original X1) and null 0.25 with m-r = 3 (X10a). All medians and quartiles agree with
x10-20261106/X1_normalized_statistics_merged.csv to relative error < 3e-13, and all failure counts are equal.

Outputs:
- `validate/records.csv`, `validate/X1_normalized_statistics.csv` (20 cells, published schema)
- `formal/records.csv` (384 outputs), `formal/X1_normalized_statistics.csv` (24 new cells)
- `X1_normalized_statistics_merged.csv`: x10-20261106/X1_normalized_statistics_merged.csv (byte-identical
  prefix) with the 24 new rows appended; 102 rows, no duplicate (null_scale, m-r, N, mode).

Results: every new cell has at most one non-stabilizing output out of 32. Over all ten m-r, removing the
null part changes the medians by at most 2.23% (dense, N = 8192, m-r = 5); previously reported as < 2% on
the four paired m-r. The factor of doubling N stays between 0.628 and 1.604.
