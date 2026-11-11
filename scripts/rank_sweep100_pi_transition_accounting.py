"""Unique simulator work, preserving bounds for incomplete diagnostic sampling."""
import argparse
import ast
import json
from pathlib import Path
import re
import tarfile
import zipfile


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def checkpoint_meta(path):
    with zipfile.ZipFile(path) as archive:blob=archive.read('meta.npy')
    assert blob[:6]==b'\x93NUMPY';size=2 if blob[6]==1 else 4;offset=8+size
    length=int.from_bytes(blob[8:offset],'little');header=ast.literal_eval(blob[offset:offset+length].decode('latin1'))
    assert header['descr'].startswith('<U')
    return json.loads(blob[offset+length:].decode('utf-32le').rstrip('\0'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--accounting',type=Path);a=p.parse_args();out=a.output
    cfg=read(out/'resolved_config.json');raw=[read(p) for p in (out/'raw').glob('pi-*.json')]
    assert len(raw)==175
    main_physical=sum(d['physical_transitions'] for d in raw)
    confirm=sum(d['physical_transitions'] for d in raw if d['seed'] in cfg['confirm_seeds'])
    charged=sum(sum(d['algorithm_actual_transitions'].values()) for d in raw)
    accounting=a.accounting or out/'slurm_accounting_before_archive.psv'
    submissions=[read(out/name) for name in ('pilot_resume_submission.json','pilot_final_resume_submission.json')]
    pilot_roots={'20184206'}|{d['pilot_resume_array'] for d in submissions}
    formal_root=read(out/'confirmation_submission.json')['formal_array']
    committed_output_jobs={str(d['slurm_job_id']) for d in raw}
    pilot_timeouts=[];formal_interruptions=[]
    for line in accounting.read_text(encoding='utf-8-sig').splitlines():
        f=line.strip().split('|')
        if len(f)<11 or not f[0] or '.' in f[1]:continue
        root=f[1].split('_')[0]
        if root in pilot_roots and f[2].startswith('TIMEOUT'):
            pilot_timeouts.append(dict(real_job_id=f[0],array_task_id=f[1],state=f[2],
                complete_output_already_committed=f[0] in committed_output_jobs))
        if root==formal_root and not f[2].startswith('COMPLETED'):
            formal_interruptions.append(dict(real_job_id=f[0],array_task_id=f[1],state=f[2]))
    assert not formal_interruptions,('Interrupted formal samples need explicit recovery accounting',formal_interruptions)
    # A killed collector can have one uncommitted chunk (or a shorter burn).
    # Per-chunk journals were not snapshotted at every pilot timeout. Final
    # cleanup removes old journals, so do not invent an exact duplicated-work
    # counter. A job that committed its complete raw output has no such loss.
    uncertain=[d for d in pilot_timeouts if not d['complete_output_already_committed']]
    pilot_possible_extra=len(uncertain)*max(cfg['data_chunk'],cfg['burn'])
    diagnostic=[]
    preflight=out.parent/'rank-sweep100-pi-preflight-20261017'
    d=read(preflight/'preflight.json')
    diagnostic.append(dict(name='original_preflight',lower=d['primitive_transitions'],upper=d['primitive_transitions'],exact=True))
    failed=out.parent/'rank-sweep100-pi-maxbench-20261017'
    d=read(failed/'preflight_progress.json');f_cfg=read(failed/'resolved_config.json')
    completed={(r['rank'],r['count']) for r in d['rows']}
    lower=sum(r['primitive_transitions'] for r in d['rows'])
    maximum_missing=sum(count+f_cfg['burn'] for rank in f_cfg['preflight_ranks'] for count in f_cfg['preflight_counts']
                        if (rank,count) not in completed)
    diagnostic.append(dict(name='OOM_maximum_batch_preflight',lower=lower,upper=lower+maximum_missing,exact=False,
        note='No collector journal in this older diagnostic; retain a bound for the incomplete second case'))
    old=out.parent/'rank-sweep100-pi-20261017'
    v=read(old/'verification.json')
    diagnostic.append(dict(name='v1_numerical_and_recovery_tests',lower=v['primitive_transitions'],upper=v['primitive_transitions'],exact=True))
    cp=old/'diagnostics/maximum-memory/checkpoints/pi-r002-s9006.npz'
    meta=checkpoint_meta(cp);lo=meta['physical'];hi=lo;pending=[]
    old_cfg=read(old/'resolved_config.json')
    snapshot=old/'diagnostics/retired_metadata/collection_and_fit_journals.tar'
    with tarfile.open(snapshot) as archive:
        for member in archive.getmembers():
            name=member.name.removeprefix('./')
            match=re.fullmatch(r'maximum-memory/pi-r002-s9006/stage-(\d+)-(dense|truncated)/collection.json',name)
            if match is None or int(match.group(1))<meta['next_stage']:continue
            entry=json.loads(archive.extractfile(member).read());actual=entry['actual'];lo+=actual;hi+=actual
            possible_extra=0
            if not entry['burn_done']:possible_extra=old_cfg['burn']
            elif entry['filled']<entry['tag']['count']:
                possible_extra=min(old_cfg.get('data_chunk',8192),entry['tag']['count']-entry['filled'])
            hi+=possible_extra
            pending.append(dict(stage=int(match.group(1)),method=match.group(2),journal_actual=actual,
                                possible_uncommitted_transitions=possible_extra))
    diagnostic.append(dict(name='retired_v1_maximum_memory_diagnostic',lower=lo,upper=hi,exact=lo==hi,
        durable_checkpoint_physical=meta['physical'],pending_collectors=pending,
        note='Stopped after replacement passed; completed checkpoint plus post-cancel collection journals, no prefix counted twice'))
    for name,filename in [('v2_numerical_and_recovery_tests','verification.json'),('v2_maximum_memory_verification','maximum_memory_verification.json')]:
        d=read(out/filename);count=d['primitive_transitions'] if 'primitive_transitions' in d else d['physical_transitions']
        diagnostic.append(dict(name=name,lower=count,upper=count,exact=True))
    result=dict(status='complete_with_explicit_diagnostic_bounds',
        main_unique_physical_transitions=main_physical,confirmation_unique_physical_transitions=confirm,
        pilot_unique_physical_transitions=main_physical-confirm,main_algorithm_charged_transitions=charged,
        main_unique_counter_scope='Durably committed unique observations; possible uncommitted pilot re-execution is bounded separately',
        formal_no_resource_interruption_verified=True,
        pilot_actual_physical_transitions_lower=main_physical-confirm,
        pilot_actual_physical_transitions_upper=main_physical-confirm+pilot_possible_extra,
        main_actual_physical_transitions_lower=main_physical,
        main_actual_physical_transitions_upper=main_physical+pilot_possible_extra,
        pilot_timeout_events=len(pilot_timeouts),
        pilot_timeouts_with_complete_output=sum(d['complete_output_already_committed'] for d in pilot_timeouts),
        possible_uncommitted_pilot_chunk_events=len(uncertain),
        pilot_possible_uncommitted_reexecuted_transitions_upper=pilot_possible_extra,
        pilot_timeout_details=pilot_timeouts,
        confirmation_algorithm_charged_transitions=sum(sum(d['algorithm_actual_transitions'].values()) for d in raw if d['seed'] in cfg['confirm_seeds']),
        diagnostic_physical_lower=sum(d['lower'] for d in diagnostic),diagnostic_physical_upper=sum(d['upper'] for d in diagnostic),
        diagnostic_breakdown=diagnostic,oracle_and_local_reanalysis_primitive_transitions=0,
        entire_PI_supplement_physical_lower=main_physical+sum(d['lower'] for d in diagnostic),
        entire_PI_supplement_physical_upper=main_physical+pilot_possible_extra+sum(d['upper'] for d in diagnostic),
        note='Formal budgets and committed unique pilot observations are exact. Actual simulator execution has explicit conservative bounds for uncommitted chunks at pilot timeouts and incomplete excluded-seed diagnostics. The upper bound is not a claim that every possible replay happened. Shared first/fullrank observations are charged to both algorithms but uniquely counted once. Historical NPG/CE learning was not repeated.')
    (out/'campaign_transition_accounting.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('diagnostic_breakdown','pilot_timeout_details')}),flush=True)


if __name__=='__main__':main()
