"""Reconcile actual AMS charges with Slurm occupancy; never equate the two."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--review',type=Path,required=True);a=p.parse_args();root=a.review
    jobs={}
    for line in (root/'slurm_final.psv').read_text(encoding='utf-8-sig').splitlines():
        f=line.strip().split('|')
        if len(f)<12 or not f[0] or '.' in f[1]:continue
        jobs[f[0]]=dict(state=f[2],seconds=int(f[4] or 0),cpus=int(f[5] or 0),memory=f[6],tres=f[7])
    with (root/'settlement/own_settled_jobs.csv').open(encoding='utf-8-sig') as stream:
        rows=list(csv.DictReader(stream))
    high=[q for q in rows if jobs[q['real_job_id']]['memory']=='7.50G']
    assert len(high)==55
    expected_extra=0
    for q in high:
        seconds=int(q['settled_elapsed_seconds']);su=float(q['displayed_rounded_SU'])
        assert abs(su-2*seconds/3600)<=.00501
        assert int(float(q['reported_total_slots']))==jobs[q['real_job_id']]['cpus']==1
        assert 'billing=1' in jobs[q['real_job_id']]['tres']
        expected_extra+=seconds/3600
    cost=json.loads((root/'compute_accounting.json').read_text())
    settled=json.loads((root/'settlement/own_settlement_summary.json').read_text())
    result=dict(status='reconciled_observed_charges',allocated_core_hours=cost['allocated_core_hours'],
        Slurm_billing_unit_hours=cost['elapsed_billing_unit_hours'],
        reported_TotalCPU_hours=cost['reported_total_cpu_hours'],
        actual_displayed_settled_SU_sum=settled['displayed_rounded_settled_SU_sum'],
        unsettled_measured_job_ids=settled['missing_measured_job_ids'],
        high_memory_PI_jobs_confirmed_two_SU_per_elapsed_hour=len(high),
        high_memory_request='7680MiB (Slurm7.50G)',
        extra_effective_core_hours_for_these_matched_PI_jobs=expected_extra,
        Slurm_billing_field_is_not_AMS_effective_core_charge=True,
        prior_budget_cap_value=300,prior_budget_cap_unit='allocated_core_hours',
        incorrect_implicit_SU_conversion_acknowledged=True,
        actual_SU_below_300=False,
        causal_status='AMS records directly show a2x rate for all55 high-memory PI jobs. Memory-equivalent charging is consistent with the official rule, but Slurm billing=1 and maxconfig -f on7680M both predicted1. Exact discrepancy in the site estimators is not isolated here.',
        correction='Do not describe216.05 billing/allocated hours as216.05 SU or say actual SUs stayed below300. Report actual AMS settled rows and missing records separately. No new compute jobs were launched for this accounting investigation.',
        official_primary_sources=['https://hprc.tamu.edu/kb/User-Guides/AMS/#non-exclusive-job',
            'https://hprc.tamu.edu/kb/User-Guides/Grace/Hardware/#usable-memory-for-batch-jobs'],
        inputs_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (root/'slurm_final.psv',root/'settlement/own_settled_jobs.csv',root/'compute_accounting.json')})
    (root/'billing_reconciliation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
