"""Maximum-budget X3 multi-order timing, after dense-only base qualification."""
import json,os,time
from pathlib import Path
import engine as e
import npg_multi

def main():
    e.require_compute();root=Path(__file__).parent;plan=json.loads((root/'large_pilot_plan.json').read_text())
    cfg=json.loads((root/plan['config']).read_text());assert cfg['experiment']=='X3' and cfg['phase']=='PILOT'
    qualification=json.loads((e.OUT/'X3'/f'pilot-npg-base{cfg["base"]}'/'QUALIFICATION-n12.json').read_text())
    assert qualification['status']=='QUALIFIED'
    system,trial=cfg['pilot_systems'][0],cfg['pilot_trials'][0];start=time.monotonic();items=[]
    for case in cfg['cases']:
        sp=case['spectrum'];s=e.plant(12,12,12,system,spectrum=sp)
        spec=dict(experiment='X3',n=12,m=12,r=12,system=system,trial=trial,spectrum=sp,null_scale=0.,base=cfg['base'],budget_multiplier=16)
        resolved=dict(cfg,eta=case['eta'],npg_batches=[16*v for v in case['npg_batches']])
        path=e.OUT/'X3/pilot-npg-large'/f'base{cfg["base"]}-{sp}-s{system}-t{trial}.json'
        d=npg_multi.execute(s,spec,resolved,[1,2,4,6,12],path)
        items.append(dict(path=str(path),seconds=d['seconds'],sha256=e.sha(path),actual_transitions=d['actual_transitions']))
        print(json.dumps(items[-1]),flush=True)
    e.save(e.OUT/'X3/pilot-npg-large'/f'BASE{cfg["base"]}_COMPLETE.json',dict(status='COMPLETE',items=items,
      seconds=time.monotonic()-start,job=os.environ['SLURM_JOB_ID'],config_sha256=e.sha(root/plan['config']),
      selection_already_frozen_by_dense_only_pilot=True))

if __name__=='__main__':main()
