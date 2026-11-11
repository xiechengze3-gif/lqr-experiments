"""Prepare the reviewed own-job accounting helper for X10b only."""
import ast
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    original=HERE.parent/'x9-20261106/accounting_x9.py'
    text=original.read_text()
    changes={
      'Own-X9':'Own-X10b',
      "OUT = Path('/scratch/user/changze/lqr_experiments/results/x9-20261106')":"OUT = Path('/scratch/user/changze/lqr_experiments/results/x10-20261106/X10b')",
      "assert ledger['study'] == 'X9' and ledger['cap_requested_SU'] == 50":"assert ledger['study'] == 'X10b' and ledger['requested_upper_cap_SU'] == 200 and ledger['actual_forecast_cap_SU'] == 160",
      "'2026-11-05'":"'2026-11-06'",
      'OWN_X9_ACCOUNTING_VERIFIED':'OWN_X10B_ACCOUNTING_VERIFIED',
      'cap_requested_SU=50, cumulative_requested_SU=':'cap_requested_SU=200, actual_forecast_cap_SU=160, measured_forecast_actual_SU=ledger[\'measured_forecast_actual_SU\'], cumulative_requested_SU=',
      'not X9 spend. Only own-X9 records retained.':'not X10b spend. Only own-X10b records retained.',
      "assert result['cumulative_requested_SU'] <= 50":"assert result['cumulative_requested_SU'] <= 200+1e-9"}
    for before,after in changes.items():
        assert before in text,before;text=text.replace(before,after)
    ast.parse(text,filename='accounting_actor.py')
    target=HERE/'accounting_actor.py'
    with target.open('x',encoding='utf-8',newline='\n') as stream:stream.write(text)
    proof=dict(status='OWN_X10B_ACCOUNTING_HELPER_PREPARED',source_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),numerical_work=0,new_jobs=0,SU=0,
        changes='New study/output/date/cap fields only; own-job filtering and Slurm/AMS overlap rules unchanged.')
    with (HERE/'ACTOR_ACCOUNTING_SOURCE_v1.json').open('x') as stream:json.dump(proof,stream,indent=2)
    print(json.dumps(proof))


if __name__=='__main__':main()
