# Current X6 delivery

X6a PROTOCOL/PILOT/FORMAL/REPORT complete; awaiting Claude's report review.
The original README and v1 source files are historical preparation checkpoints.

- Scientific report and full median/IQR table: [amendment-A1/report-v2/README.md](amendment-A1/report-v2/README.md)
- Source CSVs: `amendment-A1/deliveries/report-20365069-v4/X6a/reports/v1/`
- Verified raw estimates/models: `amendment-A1/deliveries/formal-20364803-v3/`
- Current 12 PNG/SVG figure pairs: `amendment-A1/figures-v3/`
- Portable CSV-only plotter: `amendment-A1/plot_saved_v3.py`
- X6b protocol proposal: [X6b-protocol-v1/PROTOCOL.md](X6b-protocol-v1/PROTOCOL.md)

X6a has320 fixed-gain paths,1920 Stein prefixes,1600 CE fits,12800 evaluated
rows, no hard failures and no learning updates. All transfer/archive/file hashes
were checked. These are estimation-error results, not closed-loop cost gains.

S pilot NPG bases: n24=524288, n36 right-censored >524288,
n48=2097152, n72=4194304. X6b therefore proposes a separate pilot-only n36
extension plus population R2, with an explicit requested stage-placement
exception. It will not run before Claude accepts that proposal.

X6 accounting snapshot2026-11-02T03:29:11Z: cumulative requested16.333333333/400SU;
Slurm elapsed9.542777778SU; AMS settled8.408333333SU. The last two overlap
and must not be added. X6b requested0SU so far. Old X0-X4 is separately accounted.

The live channel is ../../CLAUDE_TASK.md and ../../CODEX_REPLY.md. The user
requested continued foreground monitoring; exact ACCEPTED/REVISE instructions
control progression, with no new user confirmation and no timeout bypass.
