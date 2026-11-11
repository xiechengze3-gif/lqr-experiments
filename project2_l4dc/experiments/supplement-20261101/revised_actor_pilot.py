"""Fixed-eta/T R3 pilot over both null variants and every pilot m."""
import argparse,json,os
from pathlib import Path
import engine as e

def main():
    e.require_compute();p=argparse.ArgumentParser();p.add_argument('--base',type=int,required=True);p.add_argument('--bundle',type=int,required=True);a=p.parse_args()
    cfgpath=Path(__file__).parent/f'configs/X1_actor_base{a.base}_v2.json';cfg=json.loads(cfgpath.read_text())
    system,m,null=cfg['actor_pilot_cases'][a.bundle]
    for trial in cfg['actor_pilot_trials']:
        for alg in ('NPG','PI'):
            spec=dict(experiment='X1',n=12,m=m,r=2,system=system,trial=trial,null_scale=null,base_blocks=a.base,
                      eta=cfg['eta'],population_selected_T=len(cfg['npg_batches']),config_sha256=e.sha(cfgpath))
            path=e.OUT/f'X1/pilot/revised-base{a.base}'/alg/f's{system}-t{trial}-m{m}-null{int(null*100)}.json'
            assert not path.exists();s=e.plant(12,m,2,system,null_scale=null)
            data=e.actor_run(s,spec,cfg,alg,path);dense=[r for r in data['records'] if r['mode']=='dense']
            expected=sum((17+v)*32 for v in cfg['npg_batches'])
            assert data['actual_transitions']['dense']==data['actual_transitions']['truncated']==expected
            print(json.dumps(dict(algorithm=alg,case=spec,seconds=data['seconds'],dense_stable=all(r['stable'] for r in dense),
                                  dense_final_relative_gap=dense[-1].get('relative_gap'))),flush=True)

if __name__=='__main__':main()
