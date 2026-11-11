"""Declare paired, growing NPG batches at exactly the former total budget."""
import json
import shutil
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[1]
    original=root/'local_runs'/'fixed-value-relaxed-lstd'/'frozen'
    destination=root/'local_runs'/'fixed-value-growing-npg'/'frozen'
    assert destination.resolve().is_relative_to(root.resolve())
    if destination.exists():raise FileExistsError(destination)
    cfg=json.loads((original/'configs'/'fixed_value_suite.json').read_text())
    assert cfg['solver_rtol']==1e-6
    schedules={}
    for profile,value in cfg['profiles'].items():
        setting=value['NPG'];assert setting['stages']==64
        initial=setting['batch']//16
        assert initial*16==setting['batch']
        epochs=[initial,initial,2*initial,4*initial,8*initial,16*initial,32*initial,64*initial]
        setting['batches']=[count for count in epochs for _ in range(8)]
        assert sum(setting['batches'])==setting['batch']*64
        constant=64*(cfg['burn']+(setting['batch']+1)*cfg['horizon'])
        growing=sum(cfg['burn']+(count+1)*cfg['horizon'] for count in setting['batches'])
        assert growing==constant
        schedules[profile]=dict(epoch_batches=epochs,updates_per_epoch=8,stages=64,total_transitions=growing)
    shutil.copytree(original,destination)
    for name in ('fixed_value_run.py','fixed_value_report.py','fixed_value_pipeline.py',
                 'growing_npg_bootstrap.py','verify_growing_npg_compatibility.py'):
        shutil.copy2(root/'scripts'/name,destination/'scripts'/name)
    manifest=destination/'configs'/'fixed_value_suite.json'
    manifest.write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
    (root/'configs'/'fixed_value_growing_npg.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
    (destination/'configs'/'budget_schedule_audit.json').write_text(json.dumps(schedules,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(frozen=str(destination),schedules=schedules),indent=2))


if __name__=='__main__':main()
