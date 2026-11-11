"""Compact read-only snapshot of this study's jobs and trajectory completion."""
import collections
import json
from pathlib import Path
import subprocess
import time

OUT=Path('/scratch/user/changze/lqr_experiments/results/ce-npg-arguments-20261028')


def main():
    receipts=[json.loads(p.read_text()) for p in OUT.glob('submission-*.json')]
    jobs=[str(r['job']) for r in receipts if r.get('job')]
    raw=subprocess.check_output(['sacct','-X','-j',','.join(jobs),'-n','-P',
        '--format=JobIDRaw,State,ElapsedRaw,AllocCPUS,AllocTRES'],text=True)
    states=collections.Counter();hours=0.;billing=[]
    for line in raw.splitlines():
        cols=line.split('|')
        if len(cols)<5 or int(cols[3] or 0)==0:continue
        states[cols[1]]+=1;hours+=int(cols[2])*int(cols[3])/3600
        billing.extend(x for x in cols[4].split(',') if x.startswith('billing='))
    files=[p for p in (OUT/'raw').glob('*.json') if '.checkpoint.' not in p.name]
    terminal=collections.Counter();times=[]
    for p in (OUT/'logs').glob('formal-*.out'):
        for line in p.read_text(errors='replace').splitlines():
            if not line.startswith('{'):continue
            try:data=json.loads(line)
            except ValueError:continue
            if 'id' in data and 'seconds' in data:
                terminal[data.get('status','CE_complete')]+=1;times.append(data['seconds'])
    result=dict(epoch=time.time(),completed_new_trajectories=len(files),expected_new=1728,
        job_states=dict(states),allocated_core_hours_so_far=hours,
        all_allocated_billing_one=all(x=='billing=1' for x in billing),
        terminal_learning_statuses=dict(terminal),report_summary_exists=(OUT/'report/summary.json').exists())
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
