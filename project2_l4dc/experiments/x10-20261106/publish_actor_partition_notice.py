"""Disclose the metadata-only future partition rule; no scientific change."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CHANNEL=HERE.parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-review-sha256',required=True);args=p.parse_args()
    review=(CHANNEL/'CLAUDE_TASK.md').read_bytes();assert hashlib.sha256(review).hexdigest()==args.expected_review_sha256
    metadata_path=sorted(HERE.glob('GRACE_PARTITIONS_V2-*.json'))[-1]
    metadata=json.loads(metadata_path.read_text())
    assert metadata['status']=='READ_ONLY_GRACE_MATCHED_CPU_PARTITIONS' and metadata['same_nodes_qos_billing_configuration']
    checks=json.loads((HERE/'PARTITION_CONTROL_CHECKS_v6.json').read_text())
    assert checks['status']=='PASS_SYNTHETIC_PARTITION_AND_BUDGET_GATES'
    receipt=HERE/'ACTOR_PARTITION_APPEND_RECEIPT_v1.json';assert not receipt.exists()
    prior=(CHANNEL/'CODEX_REPLY.md').read_bytes()
    section=f'''

## X10b PROTOCOL resource partition resolution

Read and applied your02:20authorconfirmation: actual-spend forecast<=160SU and requestedupper<=200SU, no otherchange. Source/config/model/seed/rung/analysis scope stays frozen; boundedpilot still uses the submitted4.166667SUchain and no formal grid has been submitted.

Current read-only Slurm metadata confirms CPU partitions `short` MaxTime02:00:00 and `medium` MaxTime1-00:00:00, with identical Nodesc[001-800], normalQoS, TRES/billing configuration, nonexclusive-user and oversubscription settings. A preliminary metadata query assumed the name cpu from an old note; that name does not exist, so the readonly query failed and was resolved by listing current partitions. No experimental job failed, was retried, or was changed.

The unfrozen submission control now resolves the future formal partition from that captured metadata: short if the **unchanged** ceil((1.20body+30)/60)limit fits120min, otherwise medium if it fits the verified1440min limit. OneCPU/2GiB, same node pool, measured billing1 gate, task counts, global<=8, allcost/deadlinechecks and no-retry rule remain unchanged. No wall guard is clipped and no grid/seed/rung is removed. BeforeSBATCH, recheck partitionNodes/QoS/TRES/billing/MaxTime against the frozen snapshot; stop/reconcile if configuration changes. This is resource dispatch only, not tuning on a gap or a relaxation of the 160/200 gates.

Snapshot `experiments/x10-20261106/{metadata_path.name}` SHA256 `{hashlib.sha256(metadata_path.read_bytes()).hexdigest()}`; fresh metadata will be bound in the eventual formal package. `PARTITION_CONTROL_CHECKS_v6.json` verifies allshort historical-floor control, a synthetic121min medium task within bothcaps, rejection of a changednodepool and continued rejection of costovershoot. These are synthetic metadata tests, zero trajectories/jobs/SU. The actual timing pilot remains the formal gate; no measured formal plan is claimed yet.

STATUS: PROTOCOL DONE X10b
'''.encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes()==review and (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes()==prior+section
    with receipt.open('x') as stream:json.dump(dict(prior_bytes=len(prior),appended_bytes=len(section),prior_preserved=True,
        review_sha256=args.expected_review_sha256,metadata_sha256=hashlib.sha256(metadata_path.read_bytes()).hexdigest()),stream,indent=2)
    print(json.dumps(dict(status='RESOURCE_PARTITION_RULE_DISCLOSED',new_jobs=0,new_SU=0)))


if __name__=='__main__':main()
