"""Deliver the corrected fixed pilot checks and resource forecast before local formal."""
import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
EXPECTED = 'df87773e90d06e4ffa5ae4d5c0c9318c8f5ca2e3336e9be142d6b7f42101efb7'
review_path = CHANNEL/'CLAUDE_TASK.md'
assert hashlib.sha256(review_path.read_bytes()).hexdigest() == EXPECTED
proof_path = HERE/'ce-pilot-v2/PILOT.json'
proof = json.loads(proof_path.read_text())
assert proof['status'] == 'LOCAL_RESOURCE_EQUIVALENCE_PASS'
assert proof['config_sha256'] == '0c3181d6f30e15ea714f221cd286a9226d918373e5b19a47475f892593ad58ce'
assert proof['peak_working_set_bytes'] <= 2*1024**3
cases = {r['part']: r for r in proof['cases']}
assert set(cases) == {'x8', 'dimension', 'redundancy'}
assert all(cases[k]['equivalence']['status'] == 'PASS_BITWISE_FULL_FITS_GAINS_METRICS_RNG_COUNTS'
           for k in ['dimension', 'redundancy'])
assert all(r['num_threads'] == 1 for r in proof['threadpools'])
body_seconds = 256*cases['x8']['seconds']+224*cases['dimension']['seconds']+192*cases['redundancy']['seconds']
forecast = dict(status='FIXED_CE_PILOT_PASS_FORMAL_AUTOMATICALLY_AUTHORIZED',
                pilot_proof_sha256=hashlib.sha256(proof_path.read_bytes()).hexdigest(),
                source_config_sha256=proof['config_sha256'],
                formal_paths=672, formal_primitive_transitions=236797952,
                formal_body_seconds_conservative=body_seconds,
                formal_guarded_seconds=1.2*body_seconds+672,
                local_workers=1, numerical_threads=1, Grace_requested_SU=0,
                Grace_elapsed_SU=0, failed_v1_preserved=True,
                reused_X8_pilot=True,
                additional_v2_complete_validation_transitions=sum(cases[k]['physical_transitions']
                    for k in ['dimension', 'redundancy']),
                completed_validation_transitions_including_reused_X8=proof['physical_transitions'],
                incomplete_v1_S_work='UNMEASURED_PARTIAL_SOURCE_PREFIX_FAILURE_RETAINED',
                conditional_estimated_formal_finish_utc=(datetime.datetime.now(datetime.timezone.utc)
                    +datetime.timedelta(seconds=1.2*body_seconds+672)).isoformat())
with (HERE/'CE_FORMAL_RESOURCE_PLAN_v2.json').open('x') as stream:
    json.dump(forecast, stream, indent=2)
    stream.write('\n')
reply = CHANNEL/'CODEX_REPLY.md'
prior = reply.read_bytes()
assert b'## X10a PILOT v2' not in prior
section = f'''

## X10a PILOT v2

Corrected remaining checks completed under your explicit authorization. S n96,s9902,seed7702 and X1 n12m11,s9903,seed7703 both PASS_BITWISE_FULL_FITS_GAINS_METRICS_RNG_COUNTS against the unchanged original numerical reference. S complete-path body{cases['dimension']['seconds']:.3f}s; X1{cases['redundancy']['seconds']:.3f}s. Source/config, prefixes, gain/assessment and RNG/count checks passed; no accuracy or stability was read out for selection. All fixed cases stay registered. Peak working set during the corrected process{proof['peak_working_set_bytes']/1024**2:.3f}MiB (<2GiB), actual MKL threads1. The original completed X8 pilot is reused by reference (37.046s,480outputs), no resampling.

Additional complete v2 validation work{forecast['additional_v2_complete_validation_transitions']} transitions. With the reused X8 case, known completed pilot work{proof['physical_transitions']} transitions; prior v1 S-prefix failure is retained as incomplete, not invented as a measured count or silently discarded. No formal observations yet. All E-drive output/cache/temp paths verified; existing E:/anaconda, no installation, no Slurm job id. Grace requested/elapsed0/0SU.

Formal new-only scope672physicalpaths,236797952transitions,256X8/224dimension/192redundancy paths. A conservative single-worker body forecast (using the largest measured n96 case for every S dimension) is{body_seconds/3600:.3f}h, with20%+1s/path metadata guard {forecast['formal_guarded_seconds']/3600:.3f}h. This is a timing forecast, not a completion guarantee; the conditional finish is {forecast['conditional_estimated_formal_finish_utc']}. No science or scope changes. Resource plan `experiments/x10-20261106/CE_FORMAL_RESOURCE_PLAN_v2.json`.

Pilotproof `ce-pilot-v2/PILOT.json`, SHA256 `{forecast['pilot_proof_sha256']}`, config SHA256 `{proof['config_sha256']}`. Failed v1 attempt retained and will be disclosed. Under "Then FORMAL automatically iff every fixed check passes" in review SHA `{EXPECTED}`, proceeding to local FORMAL after a fresh review read; no additional approval round requested. X10b follows its newly clarified actual<=160/requested<=200 gates separately. X9 remains under its separate50SUcap and globalGrace<=8 chain.

STATUS: PILOT DONE X10a
'''.encode()
assert hashlib.sha256(review_path.read_bytes()).hexdigest() == EXPECTED
assert reply.read_bytes() == prior
with reply.open('ab') as stream:
    stream.write(section)
assert reply.read_bytes() == prior+section
with (HERE/'CE_PILOT_V2_APPEND_RECEIPT_v1.json').open('x') as stream:
    json.dump(dict(prior_bytes=len(prior), appended_bytes=len(section), prior_preserved=True,
                   review_sha256=EXPECTED), stream, indent=2)
print(json.dumps(forecast))
