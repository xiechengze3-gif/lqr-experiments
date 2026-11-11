"""Freeze the user's smaller queue; preserve the original manifest and outputs."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(r'E:\ChatGPT\Results\LQR_experiments\npg300-local-20261009')


def main():
    path=OUT/'config.json';config=json.loads(path.read_text());profiles=list(config['profiles'])
    critics=[i for i,t in enumerate(config['tasks']) if t['phase']=='critic']
    actors=[i for i,t in enumerate(config['tasks']) if t['phase']=='actor' and t['system_seed']==0
            and t['trial_seed']==0 and ((t['profile']==profiles[0] and t['r'] in (1,16,300))
                                      or (t['profile']==profiles[1] and t['r']==1))]
    assert len(critics)==50 and len(actors)==4
    blocks=len(critics)*max(config['critic_prefixes'])+sum(2*sum(config['schedules'][config['tasks'][i]['profile']]) for i in actors)
    scope=dict(name='five-system two-trial diagnostics followed by four paired full actor pilots',
        authorization='User selected multi-seed diagnostics followed by a few complete learning trajectories on 2026-10-09.',
        config_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),worker_sha256=config['runner_sha256'],
        task_ids=critics+actors,critic_tasks=50,actor_paired_tasks=4,
        actor_specs=[config['tasks'][i] for i in actors],
        collector_only_hours_if_all_arms_stay_stable=blocks*config['timing_estimate']['seconds_per_block']/3600,
        caveats='Critic has 5 systems x 2 trials; actor pilot has one system x one trial, not replicated convergence or a budget-exponent study.')
    scope_path=OUT/'active_scope.json'
    assert not scope_path.exists(), 'Scope is immutable once selected.'
    scope_path.write_text(json.dumps(scope,indent=2)+'\n',encoding='utf-8')
    receipt=dict(scope=str(scope_path),scope_sha256=hashlib.sha256(scope_path.read_bytes()).hexdigest(),**scope)
    (ROOT/'receipts'/'npg300-local-20261009-active-scope.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
