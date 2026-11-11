"""Correct a metadata-template assumption before any actor pilot; retain partial v1."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
text = (HERE/'prepare_actor_draft.py').read_text(encoding='utf-8')
replacements = {
    "DEST = HERE/'actor-draft-v1'": "DEST = HERE/'actor-draft-v2'",
    "if name in ['actor_paths.py', 'formal_driver.py', 'analyze_actor.py', 'plot_saved_actor.py']:":
        "if name in ['actor_paths.py', 'formal_driver.py', 'analyze_actor.py']:",
    "for n in cfg['n_values']:": "for n in sorted(cfg['n_values'], reverse=True):",
    "n_values=cfg['n_values'], rank=2": "n_values=sorted(cfg['n_values'], reverse=True), rank=2",
    "model_registry=registry, cap_SU=160,":
        "model_registry=registry, actual_forecast_cap_SU=160, requested_upper_cap_SU=200,",
    "DRAFT_NO_RESOURCE_AUTHORIZATION_NO_NUMERICAL_EXECUTION":
        "DRAFT_RESOURCE_AUTHORIZED_PROTOCOL_NOT_YET_FROZEN",
    "WAIT_CLAUDE_DECISION_AS_POSTED_X10_RESOURCE":
        "AUTHORIZED_BY_X10_DECISIONS_DF87773E_NO_JOBS_UNTIL_PROTOCOL_FROZEN",
    "actor-config-draft-v1.json": "actor-config-draft-v2.json",
    "ACTOR_DRAFT_SOURCE_PROOF_v1.json": "ACTOR_DRAFT_SOURCE_PROOF_v2.json",
}
for old, new in replacements.items():
    assert text.count(old) == 1, old
    text = text.replace(old, new)
target = HERE/'prepare_actor_draft_v2.py'
with target.open('x', encoding='utf-8') as stream:
    stream.write(text)
print('ACTOR_PREPARER_V2_WRITTEN_NO_SCIENTIFIC_EXECUTION')
