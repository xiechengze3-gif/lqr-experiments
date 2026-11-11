"""Append-only channel replies and the directly authorized 200-SU ledger."""
from __future__ import annotations
import argparse, hashlib, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANNEL = ROOT.parents[1]
TASK = CHANNEL / "CLAUDE_TASK.md"
REPLY = CHANNEL / "CODEX_REPLY.md"
CAP = 200.0  # User directly increased the cap in this chat after the initial 80-SU instruction.

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

def review():
    content = TASK.read_text(encoding="utf-8-sig")
    log = content.split("## Claude's review log", 1)[-1]
    value = {"checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "task_sha256": sha(TASK), "review_log": log}
    dest = ROOT / "reviews" / (str(time.time_ns())+".json")
    write(dest, value)
    return value

def spend():
    p = ROOT / "budget/ledger.json"
    if not p.exists():
        write(p, {"cap_SU": CAP, "jobs": [], "spent_SU": 0.0,
                  "requested_total_bound_SU": 0.0,
                  "note": "Includes every new pilot/formal/report job. Account-wide changes are not this study's spend."})
    value = json.loads(p.read_text(encoding="utf-8"))
    assert value["cap_SU"] == CAP
    assert sum(j["requested_bound_SU"] for j in value["jobs"]) <= CAP + 1e-10
    return value

def append(experiment, stage, body, scope='CE_ONLY'):
    checked = review()
    ledger = spend()
    if experiment=='X4' and stage=='FORMAL':
        assert scope=='DIAGNOSTIC'
        done=json.loads((ROOT/'X4/FORMAL_DIAGNOSTIC_COMPLETE.json').read_text())
        approved=json.loads((ROOT/'X4/ACCEPTED.json').read_text())
        assert approved['decision']=='ACCEPTED' and done['status']=='COMPLETE'
        assert done['outputs']==5760 and done['new_training_transitions']==0 and done['source_files']==96
    elif experiment != "X0" and stage == "FORMAL":
        label={'CE_ONLY':'CE','ACTOR':'ACTOR','NPG':'NPG'}[scope]
        completion=ROOT/experiment/f'FORMAL_{label}_COMPLETE.json'
        approval=ROOT/experiment/f'ACCEPTED_{label}.json'
        assert completion.is_file() and approval.is_file(), 'Verified completion and scoped approval required'
        done=json.loads(completion.read_text(encoding='utf-8-sig'))
        approved=json.loads(approval.read_text(encoding='utf-8-sig'))
        assert experiment in ['X1','X2','X3'] and done['status']=='COMPLETE' and done['scope']==scope
        assert done['bundles']==32
        if scope=='CE_ONLY':
            assert done['trajectories']=={'X1':288,'X2':224,'X3':192}[experiment] and approved['decision']=='ACCEPTED'
        else:
            assert approved['decision']=='ACCEPTED_CONDITIONS_SATISFIED'
            assert done['planned_actor_trajectories']=={'X1':1152,'X2':128,'X3':1440}[experiment]
            assert done['source_and_coverage_verified']
    text = f"\n## {experiment} {stage}\n\n" + body.rstrip() + "\n\n"
    text += (f"Review log reread: {checked['checked_utc']}; task SHA256 `{checked['task_sha256']}`.\n\n"
             f"Tonight new-job spend: {ledger['spent_SU']:.6f} SU; cumulative requested bound: "
             f"{ledger['requested_total_bound_SU']:.6f} / {CAP:.0f} SU. Last accounting snapshot: {ledger.get('last_accounting_utc','no jobs yet')}. "
             "The user directly authorized the 200-SU amendment in this chat; explicit protocol acceptance remains required.\n\n"
             f"STATUS: {stage} DONE {experiment}\n")
    with REPLY.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(text)

def initialize():
    ROOT.mkdir(parents=True, exist_ok=True)
    spend()
    old = ROOT / "provenance/old_files_sha256.json"
    if not old.exists():
        experiments = ROOT.parent
        paths = [p for p in experiments.rglob("*") if p.is_file() and ROOT not in p.parents
                 and not {".runtime", ".tmp", "__pycache__"}.intersection(p.relative_to(experiments).parts)]
        write(old, {str(p):sha(p) for p in paths})
    print(json.dumps(review(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("mode", choices=["init", "review", "append"])
    p.add_argument("--experiment");p.add_argument("--stage");p.add_argument("--body-file", type=Path)
    p.add_argument('--scope',choices=['CE_ONLY','ACTOR','NPG','DIAGNOSTIC'],default='CE_ONLY')
    a=p.parse_args()
    if a.mode=="init": initialize()
    elif a.mode=="review": print(json.dumps(review(), ensure_ascii=False, indent=2))
    else: append(a.experiment, a.stage, a.body_file.read_text(encoding="utf-8-sig"),scope=a.scope)
