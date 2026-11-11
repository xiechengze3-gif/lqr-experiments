# Operational amendment v2

The first invariant pilot, job20358732, failed before entering Python/science:
the SHA256SUMS text emitted on Windows contained CRLF, so Linux interpreted CR
as part of each listed filename. Slurm reports FAILED exit1:0, elapsed0 seconds,
billing1, measured0 SU. The requested0.083333SU bound remains in the ledger.

New release `supplement-20261101-x1-v2` uses an explicitly LF-only checksum file
and a separate Slurm script pointing to the v2 directory. The v1 remote release
and receipt remain unchanged. The engine and scientific configuration are
byte-identical to the preregistered v1 hashes. Only scheduler path/attempt
bookkeeping and transfer checksum newline handling change.

Retry is explicit after inspecting the failed receipt/log; no unverified job
submission or learning is replayed. No formal run is authorized by this amendment.
