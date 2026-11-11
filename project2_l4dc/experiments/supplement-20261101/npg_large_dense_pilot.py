"""Complete largest-budget dense paths for X3 resource planning, base already frozen."""
import json,os
from pathlib import Path
import engine as e
import npg_multi

def main():
    e.require_compute();root=Path(__file__).parent
    cfg=json.loads((root/'configs/X3_NPG_pilot_n12_base8192_v1.json').read_text());assert cfg['base']==8192
    q=json.loads((e.OUT/'X3/pilot-npg-base8192/QUALIFICATION-n12.json').read_text());assert q['status']=='QUALIFIED'
    case=cfg['cases'][int(os.environ['SLURM_ARRAY_TASK_ID'])];sp=case['spectrum']
    system,trial=cfg['pilot_systems'][0],cfg['pilot_trials'][0]
    spec=dict(experiment='X3',n=12,m=12,r=12,system=system,trial=trial,spectrum=sp,null_scale=0.,base=8192,budget_multiplier=16)
    resolved=dict(cfg,eta=case['eta'],npg_batches=[16*b for b in case['npg_batches']])
    path=e.OUT/'X3/pilot-npg-large'/f'base8192-{sp}-DENSE-s{system}-t{trial}.json'
    d=npg_multi.execute(e.plant(12,12,12,system,spectrum=sp),spec,resolved,[],path)
    e.save(path.parent/f'MEASURE_{sp}.json',dict(status='COMPLETE',spectrum=sp,base=8192,path=str(path),
       sha256=e.sha(path),seconds=d['seconds'],actual_transitions=d['actual_transitions'],
       planned_transitions_per_arm=d['planned_transitions_per_arm'],config_sha256=e.sha(root/'configs/X3_NPG_pilot_n12_base8192_v1.json'),
       dense_only_timing=True,base_selection_already_frozen=True,job=os.environ['SLURM_JOB_ID']))
    print(json.dumps(dict(status='COMPLETE',spectrum=sp,seconds=d['seconds'],transitions=d['actual_transitions'])),flush=True)

if __name__=='__main__':main()
