"""Map every saved pair to its real Slurm attempts without charging bundles five times."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from publish_rank_sweep100_results import read, write, sha


p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
p.add_argument('--accounting',type=Path,required=True);a=p.parse_args();out=a.output
cfg=read(out/'resolved_config.json');submission=read(out/'confirmation_submission.json')
jobs={}
for line in a.accounting.read_text(encoding='utf-8-sig').splitlines():
    f=line.strip().split('|')
    if len(f)<11 or not f[0] or '.' in f[1]:continue
    assert f[1] not in jobs
    jobs[f[1]]=dict(array_task_id=f[1],real_job_id=f[0],state=f[2],exit_code=f[3],
                   elapsed_seconds=int(f[4] or 0),allocated_CPUs=int(f[5] or 0))
resumptions=[]
for filename in ('pilot_resume_submission.json','pilot_final_resume_submission.json'):
    d=read(out/filename)
    resumptions.append((d['pilot_resume_array'],set(map(int,d['missing_task_indices'].split(',')))))
pilot_plan=[(r,s) for s in cfg['pilot_seeds'] for r in cfg['ranks']]
planned={(r,s) for s in cfg['pilot_seeds']+cfg['confirm_seeds'] for r in cfg['ranks']}
rows=[];main_attempt_ids=set();final_formal_jobs=Counter();valid_timeout_outputs=0
for path in sorted((out/'raw').glob('pi-*.json')):
    d=read(path);rank,seed=d['rank'],d['seed'];assert (rank,seed) in planned
    if seed in cfg['pilot_seeds']:
        phase='pilot';index=pilot_plan.index((rank,seed));attempt_keys=[f'20184206_{index}']
        for root,indices in resumptions:
            if index in indices:attempt_keys.append(f'{root}_{index}')
    else:
        phase='confirm';index=cfg['confirm_seeds'].index(seed)
        attempt_keys=[f"{submission['formal_array']}_{index}"]
    attempts=[jobs[key] for key in attempt_keys]
    final=[j for j in attempts if j['real_job_id']==str(d['slurm_job_id'])]
    assert len(final)==1,('Saved output does not map to a real own job attempt',rank,seed,d['slurm_job_id'])
    for attempt in attempts:main_attempt_ids.add(attempt['real_job_id'])
    valid_timeout_outputs+=int(final[0]['state'].startswith('TIMEOUT'))
    if phase=='confirm':final_formal_jobs[final[0]['real_job_id']]+=1
    rows.append(dict(rank=rank,seed=seed,phase=phase,final_real_job_id=d['slurm_job_id'],
        final_array_task_id=final[0]['array_task_id'],final_job_state=final[0]['state'],
        numerical_attempts=len(attempts),attempts_json=json.dumps(attempts,separators=(',',':')),
        raw_sha256=sha(path),policy_sha256=d['policy_sha256'],critic_sha256=d['critic_sha256'],
        identity_manifest_sha256=d['identity']['manifest_sha256'],
        physical_transitions=d['physical_transitions']))
assert len(rows)==175 and {(r['rank'],r['seed']) for r in rows}==planned
assert len(final_formal_jobs)==30 and set(final_formal_jobs.values())=={5}
with (out/'execution_provenance_by_pair.csv').open('w',newline='',encoding='utf-8-sig') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
result=dict(status='PASS',saved_paired_groups=len(rows),formal_seed_bundles=len(final_formal_jobs),
    paired_groups_per_formal_real_job=5,main_learning_real_attempt_jobs=len(main_attempt_ids),
    outputs_committed_by_jobs_later_marked_TIMEOUT=valid_timeout_outputs,
    main_attempt_Slurm_states=dict(Counter(j['state'] for j in jobs.values() if j['real_job_id'] in main_attempt_ids)),
    accounting_sha256=sha(a.accounting),pair_mapping_sha256=sha(out/'execution_provenance_by_pair.csv'),
    warning='Each formal real job has five saved rank pairs. Compute occupancy is counted once per real job, not once per pair. All initial/recovery attempts remain recorded, including timeouts after valid atomic output commits. No policy data are excluded by Slurm state.')
write(out/'execution_provenance.json',result);print(json.dumps(result),flush=True)
