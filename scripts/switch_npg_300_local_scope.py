"""Stop only this experiment's process tree near a completed-task boundary."""
import json
import time
from datetime import datetime,timezone
from pathlib import Path
import psutil
from select_npg_300_local_scope import main as select

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(r'E:\ChatGPT\Results\LQR_experiments\npg300-local-20261009')
receipt=json.loads((ROOT/'receipts'/'npg300-local-20261009-pipeline.json').read_text())
root=psutil.Process(receipt['pid'])
assert any('npg_300_local_pipeline.py' in a for a in root.cmdline()), 'PID ownership mismatch.'
progress=json.loads((OUT/'study_progress.json').read_text())
next_id=max(progress['completed_tasks'],default=-1)+1
boundary=OUT/'critic'/f'task-{next_id:03d}'/'result.json'
deadline=time.monotonic()+30
print(f'WAITING_FOR_COMPLETED_CRITIC_TASK {next_id}',flush=True)
while not boundary.exists() and time.monotonic()<deadline and root.is_running():time.sleep(.5)
tree=[p for p in root.children(recursive=True) if p.name().lower()!='conhost.exe']
for proc in tree:
    assert any(('npg_300_local_pipeline.py' in a or 'npg_300_local_study.py' in a) for a in proc.cmdline()), 'Unexpected descendant.'
for proc in reversed(tree+[root]):
    try:proc.terminate()
    except psutil.NoSuchProcess:pass
_,alive=psutil.wait_procs(tree+[root],timeout=3)
for proc in alive:
    try:proc.kill()
    except psutil.NoSuchProcess:pass
audit=dict(reason='User selected multi-seed diagnostics plus a small complete-learning pilot after measured full-grid estimate.',
           stopped_utc=datetime.now(timezone.utc).isoformat(),original_pipeline_pid=receipt['pid'],
           terminated_owned_pids=[p.pid for p in tree+[root]],
           completed_boundary=boundary.exists(),boundary_task_id=next_id,
           completed_results_preserved=sorted(p.parent.name for p in (OUT/'critic').glob('task-*/result.json')))
(OUT/'controlled_scope_switch.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
(OUT/'pipeline_status.json').write_text(json.dumps(dict(status='SUPERSEDED_BY_SELECTED_SCOPE',**audit),indent=2)+'\n',encoding='utf-8')
select()
print('SAFE_SCOPE_SWITCH_COMPLETE',flush=True)
