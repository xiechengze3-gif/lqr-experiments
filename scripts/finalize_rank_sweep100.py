"""Independent saved-policy audit and local regeneration of final artifacts."""
import argparse
import json
import shutil
import sys
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
import rank_sweep100 as e
import rank_sweep100_report as report
from actuation_redundancy import diagnostics as loss_diagnostics


def physical_accounting(cfg,out):
    main={phase:e.read(out/('report-'+phase)/'summary.json') for phase in ('pilot','confirm')}
    pilot1=out.parent/'rank-sweep100-pilot-20261016'
    old=[e.read(path) for path in (pilot1/'raw').glob('*.json')]
    assert len(old)==50,'Exploratory pilot must remain complete, including failures'
    diagnostic=[]
    paths=[pilot1,out.parent/'rank-sweep100-20261016',out.parent/'rank-sweep100-final-20261016',out]
    horizons=[8,4,4,4]
    for path,horizon in zip(paths,horizons):
        verification=e.read(path/'verification.json')
        diagnostic.append(dict(name=path.name+'_verification',
            primitive_transitions=verification['benchmark']['transitions']+2*(7+257*horizon),
            source='Saved benchmark plus two explicitly tested 256-block collectors, burn7 each'))
    benchmark=e.read(paths[1]/'remote_benchmark.json');b_cfg=benchmark['config']
    diagnostic.append(dict(name='separate_remote_runtime_benchmark',
        primitive_transitions=b_cfg['burn']+(benchmark['npg_blocks']+1)*b_cfg['horizon']+benchmark['ce_transitions']))
    for name in ('rank-sweep100-resume-tests','rank-sweep100-resume-tests-variable'):
        root=e.ROOT/'.runtime'/name
        records=[e.read(path) for path in root.glob('*/raw/*.json')];assert len(records)==4
        diagnostic.append(dict(name=name,primitive_transitions=sum(d['physical_transitions'] for d in records)))
        dest=out/'diagnostics'/name
        if not dest.exists():shutil.copytree(root,dest)
    physical_main=sum(d['physical_transitions'] for d in main.values())
    result=dict(confirmation_physical_transitions=main['confirm']['physical_transitions'],
        confirmation_algorithm_charged_transitions=main['confirm']['algorithm_charged_transitions'],
        pilot_physical_transitions=main['pilot']['physical_transitions'],
        main_unique_physical_transitions=physical_main,
        main_algorithm_charged_transitions=sum(d['algorithm_charged_transitions'] for d in main.values()),
        exploratory_v1_physical_transitions=sum(d['physical_transitions'] for d in old),
        diagnostic_physical_transitions=sum(d['primitive_transitions'] for d in diagnostic),
        diagnostic_breakdown=diagnostic,oracle_primitive_transitions=0,
        note='Shared algorithm observations are charged to each algorithm but physically simulated once. Migrated pilot prefixes and CE datasets are counted once. Pilots/diagnostics do not enter the fresh30-seed success denominators.')
    result['entire_campaign_unique_physical_transitions']=physical_main+result['exploratory_v1_physical_transitions']+result['diagnostic_physical_transitions']
    e.atomic_json(out/'campaign_transition_accounting.json',result)


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();cfg=e.read(a.manifest);cfg['output']=str(a.output);out=a.output
    expected=(len(cfg['pilot_seeds'])+len(cfg['confirm_seeds']))*len(cfg['ranks'])*2
    sources=list((out/'raw').glob('*.json'));assert len(sources)==expected,(len(sources),expected)
    planned={(route,rank,seed) for route in ('npg','ce') for rank in cfg['ranks']
             for seed in cfg['pilot_seeds']+cfg['confirm_seeds']}
    observed={(d['route'],d['rank'],d['seed']) for d in (e.read(path) for path in sources)}
    assert observed==planned and len(observed)==len(sources),'Incomplete or duplicate planned coverage'
    verification=e.read(out/'verification.json');identity=verification['identity']
    for source,digest in identity['sources'].items():assert e.sha(e.ROOT/source)==digest,('Reanalysis numerical source differs',source)
    checked=0;unstable_checked=0;maximum=0.;full_rank=0;first_pair_checks=0;first_pair_error=0.
    systems={};private={};system_checks=[];common=None;decomposition=[]
    for rank in cfg['ranks']:
        with np.load(out/'systems'/f'r{rank:03d}.npz',allow_pickle=False) as arrays:
            systems[rank]={key:(float(arrays[key]) if arrays[key].ndim==0 else arrays[key].copy())
                           for key in ('A','B','Q','R','W','K0','Kstar','Jstar','initial_gap')}
            u,v,f0,p0=(arrays[key].copy() for key in ('U','V','F0','P0'))
            s=systems[rank]
            private[rank]=dict(Beff=cfg['b']*u[:,:rank],O=v,Pstar=arrays['Pstar'].copy())
            np.testing.assert_allclose(u.T@u,np.eye(cfg['n']),atol=2e-13)
            np.testing.assert_allclose(v.T@v,np.eye(cfg['n']),atol=2e-13)
            np.testing.assert_allclose(s['B'],cfg['b']*u[:,:rank]@v[:,:rank].T,atol=2e-13)
            np.testing.assert_allclose(s['A']-s['B']@s['K0'],f0,atol=2e-13)
            np.testing.assert_allclose(f0@u[:,0],.75*u[:,0],atol=2e-13)
            assert np.linalg.eigvalsh(p0)[0]>0 and np.linalg.matrix_rank(s['B'],tol=1e-10)==rank
            if common is None:common=(u,v,s['A'],s['K0'],f0,p0)
            else:
                for expected,actual in zip(common,(u,v,s['A'],s['K0'],f0,p0)):np.testing.assert_array_equal(expected,actual)
            q,_=e.evaluate(s,s['Kstar']);assert q['stable'] and q['gap']<1e-8
            system_checks.append(dict(rank=rank,status='PASS',shared_U_V_A_K0_F0_P0=True,
                                      B_formula_max_error=float(np.max(abs(s['B']-cfg['b']*u[:,:rank]@v[:,:rank].T)))))
    for i,path in enumerate(sorted(sources)):
        data=e.read(path);assert data['identity']==identity
        policy=out/'policies'/path.with_suffix('.npz').name
        assert e.sha(policy)==data['policy_sha256']
        with np.load(policy,allow_pickle=False) as archive:
            # NpzFile indexing decompresses the whole member each time. Cache
            # each stack once before visiting its individual checkpoints.
            stored={key:archive[key] for key in archive.files}
            if data['route']=='npg':
                first=[r for r in data['records'] if r['stage']==1]
                if all(r['failure']!='numerical_failure' for r in first):
                    k0=systems[data['rank']]['K0']
                    dense_z=(k0-stored['dense'][1])/cfg['eta']-k0
                    truncated_z=(k0-stored['truncated'][1])/cfg['eta']-k0
                    expected_z=e.corrected(dense_z,'truncated',data['rank'])
                    error=float(np.max(abs(truncated_z-expected_z)));first_pair_error=max(first_pair_error,error)
                    np.testing.assert_allclose(truncated_z,expected_z,rtol=5e-9,atol=5e-10)
                    first_pair_checks+=1
            if data['rank']==cfg['n']:
                if data['route']=='npg':np.testing.assert_array_equal(stored['dense'],stored['truncated'])
                else:np.testing.assert_array_equal(stored['policies'][::2],stored['policies'][1::2])
                full_rank+=1
            for j,row in enumerate(data['records']):
                if not row['observed'] or row['failure'] in ('numerical_failure','riccati_failure'):continue
                k=stored[row['method']][row['stage']] if data['route']=='npg' else stored['policies'][j]
                assert np.isfinite(k).all()
                q,_=e.evaluate(systems[data['rank']],k);assert q['stable']==row['stable']
                if q['stable']:
                    for eps in (verification['epsilon'],verification['epsilon']/2):
                        assert (q['gap']<=eps)==(row['gap']<=eps),'Reanalysis changed target classification'
                for key in ('rho','cost','gap','relative_gap'):
                    if q[key] is None:assert row[key] is None
                    else:
                        diff=abs(q[key]-row[key]);maximum=max(maximum,diff)
                        np.testing.assert_allclose(q[key],row[key],rtol=1e-8,atol=2e-8)
                checked+=int(q['stable']);unstable_checked+=int(not q['stable'])
                # Post-hoc truth is confined to this evaluator. The learner never
                # sees the action-space projection or these cost decompositions.
                if data['route']=='npg' and row['stage']==len(e.schedule(cfg)) and q['stable']:
                    diag=loss_diagnostics(systems[data['rank']],private[data['rank']],k)
                    decomposition.append(dict(rank=data['rank'],seed=data['seed'],method=row['method'],
                        phase='pilot' if data['seed'] in cfg['pilot_seeds'] else 'confirm',
                        gap=diag['gap'],redundant_loss=diag['redundant_loss'],effective_loss=diag['effective_loss'],
                        redundant_fraction=diag['redundant_loss']/max(diag['gap'],1e-30),
                        decomposition_residual=diag['decomposition_residual'],
                        performance_identity_residual=diag['performance_identity_residual']))
        if (i+1)%25==0:print(json.dumps(dict(audit_progress=i+1,total=len(sources))),flush=True)
    audit=dict(status='PASS',stable_policies_checked=checked,unstable_policies_checked=unstable_checked,
               full_rank_paired_task_checks=full_rank,maximum_absolute_recompute_difference=maximum,
               source_tasks=len(sources),identity=identity,system_checks=system_checks,
               first_estimate_pairing_checks=first_pair_checks,first_estimate_pairing_max_error=first_pair_error,
               target_classifications_recomputed=True)
    e.atomic_json(out/'audit.json',audit)
    for phase in ('pilot','confirm'):
        original=out/'reporting_original_remote'/('report-'+phase)
        if not original.exists():shutil.copytree(out/('report-'+phase),original)
    for phase in ('pilot','confirm'):report.make_report(cfg,phase)
    report.csv_write(out/'report-confirm'/'endpoint_loss_decomposition_all_seeds.csv',decomposition)
    decomp_summary=[]
    for rank in cfg['ranks']:
        for method in ('dense','truncated'):
            group=[r for r in decomposition if r['rank']==rank and r['method']==method and r['phase']=='confirm']
            if not group:continue
            row=dict(rank=rank,method=method,stable_seeds=len(group),offline_true_projection_only=True)
            for key in ('gap','redundant_loss','effective_loss','redundant_fraction'):
                row[key+'_median']=float(np.median([r[key] for r in group]))
            decomp_summary.append(row)
    report.csv_write(out/'report-confirm'/'endpoint_loss_decomposition_summary.csv',decomp_summary)
    physical_accounting(cfg,out)
    import scipy,numba,matplotlib,threadpoolctl
    e.atomic_json(out/'local_reanalysis_environment.json',dict(python=sys.executable,python_version=sys.version,
        numpy=np.__version__,scipy=scipy.__version__,numba=numba.__version__,matplotlib=matplotlib.__version__,
        threadpoolctl=threadpoolctl.__version__,backend='local saved-policy audit and statistics; no new learning samples'))
    issues=e.ROOT/'receipts/rank-sweep100-run-issues.json'
    shutil.copyfile(issues,out/'run_issues.json')
    provenance=out/'reporting_source';provenance.mkdir(exist_ok=True)
    for source in ('rank_sweep100_report.py','finalize_rank_sweep100.py','test_rank_sweep100_resume.py'):
        shutil.copyfile(e.ROOT/'scripts'/source,provenance/source)
    e.atomic_json(provenance/'hashes.json',{x.name:e.sha(x) for x in provenance.glob('*.py')})
    derived={str(path.relative_to(out)).replace('\\','/'):e.sha(path)
             for folder in ('report-pilot','report-confirm','reporting_source')
             for path in (out/folder).rglob('*') if path.is_file()}
    e.atomic_json(out/'derived_reports_sha256.json',derived)
    print(json.dumps(audit),flush=True)


if __name__=='__main__':
    with threadpool_limits(limits=1):main()
