"""Stdlib-only X6b completion receipt: coverage, states, source and sample counts.

This is not a numerical analysis. Matrix artifact hashes/updates/decomposition
are checked by the separately gated compute-node REPORT. No missing task or
absorbing failure is silently dropped, resumed, retried, or declared successful.
"""
import argparse
import datetime
import hashlib
import json
import math
import subprocess
from pathlib import Path

BASE=Path('/scratch/user/changze/lqr_experiments/results/x6-20261101')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True)
    p.add_argument('--raw',type=Path,required=True);a=p.parse_args()
    assert a.raw.resolve()==BASE/'X6b/formal-v1'
    c=json.loads(a.config.read_text());digest=sha(a.config)
    assert c['status']=='FORMAL_FROZEN'
    for name,value in c['scientific_sources'].items():assert sha(a.config.parent/name)==value
    receipts=[]
    for path in (BASE/'submissions').glob('*.json'):
        row=json.loads(path.read_text())
        if row['experiment']=='X6b' and row['stage']=='FORMAL':
            assert row['approval']['formal_config_sha256']==digest
            assert row['status']=='SUBMITTED' and row['job']
            receipts.append(row)
    assert {r['plan']['id'] for r in receipts}=={g['id'] for g in c['formal_groups']}
    jobs={r['job'] for r in receipts};assert len(jobs)==len(c['formal_groups'])
    text=subprocess.check_output(['sacct','-X','-j',','.join(sorted(jobs)),'-n','-P',
        '--format=JobID%48,State,ElapsedRaw'],universal_newlines=True)
    states={line.split('|')[0]:line.split('|')[1] for line in text.splitlines() if line.strip()}
    expected={job+'_'+str(i) for job in jobs for i in range(32)}
    if set(states)!=expected or any(value!='COMPLETED' for value in states.values()):
        print(json.dumps(dict(status='NOT_ALL_COMPLETED',expected=len(expected),observed=len(states),
            state_counts={value:list(states.values()).count(value) for value in set(states.values())})))
        return
    counts=dict(tasks=0,paired_paths=0,raw_stage_artifacts=0,checkpoint_pairs=0,primitive_transitions=0)
    hashes=[];failure_counts={arm:0 for arm in ['dense','truncated']}
    for group in c['formal_groups']:
        schedule_by_rung={s['rung']:s for s in c['all_schedules'] if s['n']==group['n']}
        for index in range(32):
            task=a.raw/group['id']/('task-'+str(index));done=json.loads((task/'DONE.json').read_text())
            assert done['status']=='COMPLETE' and done['config_sha256']==digest
            assert done['source_sha256']==c['scientific_sources']['formal_driver.py']
            assert done['actor_sha256']==c['scientific_sources']['actor_paths.py']
            assert done['engine_sha256']==c['scientific_sources']['frozen_engine.py']
            assert done['index']==index and done['group']==group
            assert len(done['paths'])==len(group['runs'])
            system=c['formal_systems'][index//4];seed=c['formal_sampling_seeds'][index%4]
            model=c['model_registry'][f'n{group["n"]}-s{system}']
            assert done['model']==model
            for run,entry in zip(group['runs'],done['paths']):
                path=task/entry['path'];receipt=path/'DONE.json'
                assert sha(receipt)==entry['done_sha256']
                data=json.loads(receipt.read_text());alg=run['algorithm'];rung=run['rung']
                assert data['status']=='COMPLETE' and data['algorithm']==alg
                assert data['source_sha256']==c['scientific_sources']['actor_paths.py']
                assert data['engine_sha256']==c['scientific_sources']['frozen_engine.py']
                spec=data['spec'];assert (spec['n'],spec['system'],spec['seed'],spec['rung'])==(group['n'],system,seed,rung)
                schedule=schedule_by_rung[rung];batches=schedule['batches'][alg]
                M=schedule['primitive_per_arm_per_algorithm']
                assert data['primitive_transitions']==dict(dense=M,truncated=M)
                records={(r['stage'],r['arm']):r for r in data['records']}
                artifacts={(r['stage'],r['arm']):r for r in data['artifacts']}
                assert len(records)==len(data['records'])==2*(len(batches)+1)
                assert len(artifacts)==len(data['artifacts'])==2*len(batches)
                used=0;dead=dict(dense=False,truncated=False);padding=dict(dense=0,truncated=0)
                for stage in range(len(batches)+1):
                    if stage:used+=(batches[stage-1]+17)*16
                    for arm in ['dense','truncated']:
                        row=records[stage,arm];assert row['primitive_transitions']==used
                        if stage:
                            assert row['padding_stage']==dead[arm]
                            if dead[arm]:
                                padding[arm]+=(batches[stage-1]+17)*16
                                assert not row['stable']
                            assert (path/artifacts[stage,arm]['path']).is_file()
                        assert row['padding_transitions']==padding[arm]
                        if row['stable']:
                            assert math.isfinite(row['gap']) and math.isfinite(row['relative_gap'])
                            assert row['gap']>=-1e-12
                        else:
                            assert row['gap'] is None and row['relative_gap'] is None
                            dead[arm]=True
                    if stage:
                        checkpoint=json.loads((path/f'checkpoint-{stage:03d}.json').read_text())
                        assert checkpoint['status']=='COMPLETE_STAGE' and checkpoint['stage']==stage
                        assert checkpoint['dead']==dead and checkpoint['padding_transitions']==padding
                        assert checkpoint['total_primitive_transitions']==dict(dense=used,truncated=used)
                        assert (path/f'checkpoint-{stage:03d}.npz').is_file()
                assert data['padding_transitions']==padding
                for arm in dead:failure_counts[arm]+=dead[arm]
                counts['paired_paths']+=1;counts['primitive_transitions']+=2*M
                counts['raw_stage_artifacts']+=2*len(batches);counts['checkpoint_pairs']+=len(batches)
                hashes.append(dict(path=receipt.relative_to(a.raw).as_posix(),sha256=entry['done_sha256']))
            counts['tasks']+=1
    assert counts['tasks']==len(c['formal_groups'])*32
    assert counts['paired_paths']==len(c['n_values'])*4*2*32
    assert counts['primitive_transitions']==sum(s['primitive_per_arm_per_algorithm']*128 for s in c['all_schedules'])
    result=dict(status='COMPLETE_COVERAGE_COUNTS_SOURCES',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        config_sha256=digest,validator_sha256=sha(Path(__file__)),counts=counts,
        jobs=sorted(jobs),failure_counts=failure_counts,paired_path_receipts=hashes,
        numerical_checks='Pending separately authorized REPORT:raw/checkpoint hashes,update equivalence,diagnostics and cost identities',
        zero_new_transitions=True)
    proof=a.raw/'FORMAL_COMPLETE_v1.json';assert not proof.exists()
    proof.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='paired_path_receipts'}))


if __name__=='__main__':main()
