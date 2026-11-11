"""Prepare a measured whole-grid plan; stdlib only, never submits a job.

Resource observations alone choose coverage. Model files are copied byte-for-byte
from the frozen S system registry, without reading old formal performance.
"""
import argparse
import ast
import csv
import hashlib
import json
import math
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--resource',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    assert not args.out.exists();args.out.mkdir(parents=True)
    config=json.loads((ROOT/'resolved-v1/resolved-config.json').read_text())
    assert config['selected_NPG_T']==16 and config['selected_PI_T']==8 and config['eta']==.2
    costs=[];groups=[]
    for n in config['n_values']:
        path=args.resource/f'X6b/resource-v1/timing-n{n}/timing.json'
        measurement=json.loads(path.read_text());assert measurement['status']=='COMPLETE_RESOURCE_ONLY'
        assert len(measurement['rows'])==16
        for schedule in [s for s in config['all_schedules'] if s['n']==n]:
            for algorithm,T in [('NPG',16),('PI',8)]:
                rows=[r for r in measurement['rows'] if r['rung']==schedule['rung'] and r['algorithm']==algorithm]
                assert {r['arm'] for r in rows}=={'dense','truncated'}
                count=max(schedule['batches'][algorithm]);assert all(r['max_stage_blocks']==count for r in rows)
                collector=rows[0]['collector_seconds'];assert collector==rows[1]['collector_seconds']
                # Both arms collect independently at their own policies; no halving for paired RNG.
                collect_seconds=2*collector/(count+17)*(sum(schedule['batches'][algorithm])+17*T)
                update_write_seconds=T*sum(r['update_seconds']+r['artifact_write_seconds'] for r in rows)
                # Explicit conservative allowance for evaluations/checkpoints:1s per arm/stage.
                evaluation_checkpoint_allowance=2*T
                costs.append(dict(n=n,rung=schedule['rung'],algorithm=algorithm,
                    primitive_per_arm=schedule['primitive_per_arm_per_algorithm'],
                    measured_max_stage_blocks=count,measured_one_collector_seconds=collector,
                    measured_max_rss_KiB=max(r['max_rss_KiB'] for r in rows),
                    forecast_two_collectors_seconds=collect_seconds,
                    forecast_updates_writes_seconds=update_write_seconds,
                    evaluation_checkpoint_allowance_seconds=evaluation_checkpoint_allowance,
                    science_forecast_seconds=collect_seconds+update_write_seconds+evaluation_checkpoint_allowance,
                    timing_input_sha256=sha(path)))
        for kind in ['low-three','full-NPG','full-PI']:
            cells=[c for c in costs if c['n']==n and ((kind=='low-three' and c['rung']<1)
                   or (kind=='full-'+c['algorithm'] and c['rung']==1))]
            assert len(cells)==(6 if kind=='low-three' else 1)
            raw_seconds=sum(c['science_forecast_seconds'] for c in cells)
            # One minute startup/warmup per allocation, then30% margin and integer-minute ceiling.
            wall=math.ceil(1.3*(raw_seconds+60)/60)
            groups.append(dict(id=f'n{n}-{kind}',n=n,runs=[dict(algorithm=c['algorithm'],rung=c['rung'],
                rung_label={1/64:'r0015625',1/16:'r00625',1/4:'r025',1.:'r1'}[c['rung']]) for c in cells],
                tasks=32,cpus=1,memory_MiB=2048,wall_minutes=wall,
                partition='short' if wall<=120 else 'medium',concurrency=8,
                forecast_seconds_per_task=raw_seconds+60,requested_bound_SU=32*wall/60))
    # Cap test includes prior19 requested and a reserved6.5SU report envelope.
    formal=sum(g['requested_bound_SU'] for g in groups)
    alternatives=[]
    for dims in [[24,36,48,72],[24,36,48],[24,36]]:
        value=sum(g['requested_bound_SU'] for g in groups if g['n'] in dims)
        alternatives.append(dict(n_values=dims,formal_requested_SU=value,
            cumulative_with_report_SU=19+value+6.5,fits_400=19+value+6.5<=400))
    chosen=next(a for a in alternatives if a['fits_400'])
    proposed_cut=[n for n in config['n_values'] if n not in chosen['n_values']]
    config['resource_n_values']=config['n_values']
    config['n_values']=chosen['n_values']
    config['all_schedules']=[s for s in config['all_schedules'] if s['n'] in config['n_values']]
    groups=[g for g in groups if g['n'] in config['n_values']]
    formal=sum(g['requested_bound_SU'] for g in groups)
    config['status']='FORMAL_FROZEN';config['formal_groups']=groups
    config['scientific_sources']={name:sha(ROOT/name) for name in
        ['frozen_engine.py','actor_paths.py','formal_driver.py','analyze_actor.py','plot_saved_actor.py']}
    config['model_registry']={}
    prior=ROOT.parent/'amendment-A1/deliveries/formal-20364803-v3/X6a/formal'
    for n in config['n_values']:
        for index,system in enumerate(config['formal_systems']):
            source=prior/f'task-{4*index}'/f'S-n{n}'
            receipt=json.loads((source/'receipt.json').read_text())
            assert receipt['spec']['system']==system and receipt['spec']['n']==n and receipt['spec']['family']=='S'
            model=source/'model.npz';assert sha(model)==receipt['model_sha256']
            relative=f'models/n{n}-s{system}.npz';destination=args.out/relative
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(model,destination)
            config['model_registry'][f'n{n}-s{system}']=dict(path=relative,sha256=sha(destination),
                certificate=receipt['certificate'],source_model=str(model),source_receipt_sha256=sha(source/'receipt.json'))
    target=args.out/'formal-config.json';target.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    for name in config['scientific_sources']:
        ast.parse((ROOT/name).read_text(encoding='utf-8-sig'))
    with (args.out/'measured-costs.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(costs[0]));writer.writeheader();writer.writerows(costs)
    plan=dict(status='PREPARED_AWAITING_EXPLICIT_FORMAL_ACCEPTANCE',prior_requested_SU=19,
        formal_requested_SU=formal,reserved_report_SU=6.5,total_requested_with_report_SU=19+formal+6.5,
        cap_requested_SU=400,groups=groups,alternatives=alternatives,formal_config_sha256=sha(target),
        source_sha256=sha(Path(__file__)),scientific_sources=config['scientific_sources'],
        group_note='Low3rungs x2alg bundled; full-NPG and full-PI separate. Every path starts freshK0.',
        tasks=len(groups)*32,paired_paths=len(config['n_values'])*4*2*32,arms=len(config['n_values'])*4*2*32*2,
        training_primitive_transitions=sum(s['primitive_per_arm_per_algorithm']*128 for s in config['all_schedules']),
        proposed_omitted_dimensions=proposed_cut,
        retries=0,threads=1,resource_only_measurements=True)
    (args.out/'formal-plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(plan))


if __name__=='__main__':main()
