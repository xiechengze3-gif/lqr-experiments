"""Report the stopped local pilot and concrete correction before any retry."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
EXPECTED = '97173f645c72d54497aa5594e7d31bb4e32a26935b81e0adada4b9897b1b474e'
task = CHANNEL/'CLAUDE_TASK.md'
assert hashlib.sha256(task.read_bytes()).hexdigest() == EXPECTED
assert not (HERE/'ce-formal-v1').exists() and not (HERE/'ce-pilot-v2').exists()
x8_path = HERE/'ce-pilot-v1/x8/DONE.json'
x8 = json.loads(x8_path.read_text())
assert x8['status'] == 'COMPLETE' and len(x8['records']) == 480
assert not (HERE/'ce-pilot-v1/dimension/DONE.json').exists()
fix = json.loads((HERE/'CE_IMPORT_CORRECTION_v2.json').read_text())
assert fix['status'] == 'CORRECTION_PREPARED_NO_NUMERICAL_RETRY'
body = f'''# X10a pilot stopped — import correction prepared, no automatic retry

Your X10 GO says: "Otherwise stop and report." The local pilot did not finish all checks. It stopped with **NameError: name 'json' is not defined** in the portable extraction of original ce_prefixes at the first dimension-case prefix. This is my wrapper's omitted dependency import, not a controller/estimator accuracy result. I have stopped this pilot and have not retried it or started FORMAL.

Completed before failure: original unchanged X8 rho.85,system9901,seed7701 pilot,480outputs,262656physicaltransitions, **{x8['seconds']:.3f}s**; only resource/count metadata was read out. The n96 S case created its model and reached the first N2048 yield where JSON RNG-state serialization failed; no complete-prefix/complete-path receipt was emitted, so no completed S trajectory is claimed. Its in-flight work is retained as incomplete, with no invented measured partial count. The X1 validation trajectory was not collected. Formal observations0; Grace jobs/SUs0.

Actual preflight verifiedE:/anaconda/python.exe, all output/temp/cachepaths onE,6,934,188,032availablephysicalbytes,71,275,458,560Efreebytes,1thread controls and matching frozen source hashes before numerical work. The earlier launcher-only PowerShell JSON case-key issue was corrected before any pilot directory existed and did not change a scientific source. All v1 code/config, completed X8 resource receipt and incomplete S files remain untouched.

Concrete correction is prepared for review: `experiments/x10-20261106/ce-src-v2/`, `ce-config-protocol-v2.json`, `CE_IMPORT_CORRECTION_v2.json`, `Launch-CE-v3.ps1`. Portable S module adds **import json**; both original model/ce_prefixes function source texts are exactly unchanged. A stdlib symbol-table check now verifies that both extracted S functions and the original numerical CE reference have all global dependencies resolved. `run_shared_ce`, `run_x8` and the numerical equivalence routine are source-text-identical. Other changes are versioned output/config paths and reuse of the already complete X8 pilot by reference, with its source/wrapper/case/count hashes checked. No X8 pilot resampling is proposed. No new tuning, order, model, seed, budget or analysis metric is selected.

V2 config SHA256 `{fix['config_sha256']}`. V1 X8 pilot receipt SHA256 `{hashlib.sha256(x8_path.read_bytes()).hexdigest()}`. The v2 scientific-source hashes and static checks are in CE_IMPORT_CORRECTION_v2.json. **No v2 numerical execution has occurred.** Please authorize the corrected remaining S/X1 resource/equivalence checks, using their unchanged registered pilot ids/seeds/grids, in new ce-pilot-v2 paths. FORMAL remains conditional on every fixed check passing; the prior failed attempt is retained and disclosed. X10a0GraceSU; X10b remains separately stopped for its resource decision. X9 continues under the accepted formal chain.
'''
with (HERE/'CE_PILOT_FAILURE_v1.md').open('x', encoding='utf-8') as stream:
    stream.write(body)
reply = CHANNEL/'CODEX_REPLY.md'
prior = reply.read_bytes()
assert b'## X10a PILOT failure' not in prior
section = ('\n\n## X10a PILOT failure\n\n'+body.split('\n', 1)[1].lstrip()
           +'\nSTATUS: PILOT STOPPED X10a\n').encode()
assert hashlib.sha256(task.read_bytes()).hexdigest() == EXPECTED and reply.read_bytes() == prior
with reply.open('ab') as stream:
    stream.write(section)
assert reply.read_bytes() == prior+section
with (HERE/'CE_PILOT_FAILURE_APPEND_RECEIPT_v1.json').open('x') as stream:
    json.dump(dict(prior_bytes=len(prior), appended_bytes=len(section), prior_preserved=True,
                   review_sha256=EXPECTED, new_SU=0, automatic_retries=0), stream, indent=2)
print('CE_PILOT_FAILURE_AND_CONCRETE_V2_REPORTED_NO_RETRY')
