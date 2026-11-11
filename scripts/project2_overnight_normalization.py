"""Pair return variance by policy as well as plant, trial, horizon, and budget."""
import csv
import json
from pathlib import Path
import shutil
import sys

BASE=Path('/scratch/user/changze/lqr_experiments')
ROOT=BASE/'releases/project2-overnight-20261020'
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT)]
import numpy as np
import project2_overnight as science


def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))


def main():
    science.require_compute();out=BASE/'results/project2-overnight-20261020';dest=out/'derived'
    results=read(out/'report/one_step_outputs.csv');noise=read(out/'report/null_noise.csv')
    def key(r):return tuple(int(r[k]) for k in ('n','m','r','H','seed','trial','N'))+(r['policy'],)
    delta={key(r):float(r['delta_variance']) for r in noise}
    assert len(delta)==len(noise),'Every noise record must have a unique policy-aware pairing key'
    points=[];fits=[]
    for variable in ('n','r'):
        for method in ('dense','known_rank'):
            selected=[r for r in results if r['algorithm']=='NPG' and r['method']==method and r['policy']=='Kstar'
                and int(r['N'])==131072 and int(r['H'])==16 and int(r['trial'])<10
                and int(r['n'])==int(r['m']) and (int(r['r'])==4 if variable=='n' else int(r['n'])==50)]
            grouped={}
            for r in selected:grouped.setdefault(int(r[variable]),[]).append(r)
            current=[]
            for value,rows in sorted(grouped.items()):
                errors=[float(r['Z_error_fro2']) for r in rows]
                normalized=[float(r['Z_error_fro2'])/delta[key(r)] for r in rows]
                record=dict(variable=variable,method=method,value=value,repetitions=len(rows),
                    Z_error_fro2_median=float(np.median(errors)),
                    Z_error_over_delta_variance_median=float(np.median(normalized)))
                paired_median_variance=float(np.median([delta[key(r)] for r in rows]))
                assert .5 < record['Z_error_over_delta_variance_median']/(record['Z_error_fro2_median']/paired_median_variance)<2
                points.append(record);current.append(record)
            for metric in ('Z_error_fro2_median','Z_error_over_delta_variance_median'):
                x=np.log([r['value'] for r in current]);y=np.log([r[metric] for r in current])
                coefficients=np.polyfit(x,y,1);residual=np.sum((y-np.polyval(coefficients,x))**2)
                fits.append(dict(variable=variable,method=method,metric=metric,slope=float(coefficients[0]),
                    log_R2=float(1-residual/max(np.sum((y-y.mean())**2),1e-30))))
    for name in ('fixed_policy_dimension_rank_points.csv','fixed_policy_fits.json','summary.json'):
        source=dest/name;original=dest/(source.stem+'_original_v5'+source.suffix)
        assert source.exists() and not original.exists();shutil.copyfile(source,original)
    old_points=read(dest/'fixed_policy_dimension_rank_points_original_v5.csv')
    assert len(old_points)==len(points)
    for a,b in zip(old_points,points):np.testing.assert_allclose(float(a['Z_error_fro2_median']),b['Z_error_fro2_median'],rtol=0,atol=0)
    science.write_csv(dest/'fixed_policy_dimension_rank_points.csv',points)
    correction=dict(reason='Return variance pairing key now includes policy; K0 no longer overwrites the Kstar central cell',
        raw_error_medians_unchanged=True,learning_results_unchanged=True,unique_noise_keys=len(delta))
    science.atomic_json(dest/'fixed_policy_fits.json',dict(fits=fits,definition='same N,H; four plants x first ten trials',correction=correction))
    summary=json.loads((dest/'summary.json').read_text());summary['fixed_policy_fits']=fits;summary['normalization_correction']=correction
    science.atomic_json(dest/'summary.json',summary)
    print(json.dumps(dict(status='PASS',fits=fits,correction=correction)),flush=True)


if __name__=='__main__':main()
