"""Additional descriptive analysis of saved CE500 results; no simulations."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    with (a.input/'sample_complexity.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    with (a.input/'fixed_budget_rank_scaling.csv').open(encoding='utf-8-sig',newline='') as f:fixed=list(csv.DictReader(f))
    ranks=[2,4,8,32];results=[]
    for target in [.1,.05]:
        data=[next(q for q in rows if int(q['rank'])==r and q['method']=='truncated' and float(q['relative_target'])==target) for r in ranks]
        lo=[float(q['previous_tested_budget']) for q in data];hi=[float(q['N_hat_90']) for q in data]
        slope_lo=0.;slope_hi=float('inf')
        for i in range(len(ranks)):
            for j in range(i+1,len(ranks)):
                delta=ranks[j]-ranks[i]
                slope_lo=max(slope_lo,(lo[j]-hi[i])/delta)
                slope_hi=min(slope_hi,(hi[j]-lo[i])/delta)
        proportional_lo=max(l/r for l,r in zip(lo,ranks));proportional_hi=min(h/r for h,r in zip(hi,ranks))
        example=None
        if slope_lo<slope_hi:
            slope=(slope_lo+slope_hi)/2
            intercept_lo=max(l-slope*r for l,r in zip(lo,ranks));intercept_hi=min(h-slope*r for h,r in zip(hi,ranks))
            intercept=(intercept_lo+intercept_hi)/2
            prediction=[intercept+slope*r for r in ranks]
            assert all(l<x<=h for l,x,h in zip(lo,prediction,hi))
            example=dict(intercept=intercept,slope=slope,predicted_N=prediction)
        results.append(dict(relative_target=target,ranks=ranks,previous_failed_grid_points=lo,first_successful_grid_points=hi,
            N_per_rank=[h/r for h,r in zip(hi,ranks)],
            affine_line_compatible_with_all_grid_brackets=slope_lo<slope_hi,
            affine_slope_compatible_interval=[slope_lo,slope_hi],example_compatible_affine_line=example,
            proportional_line_compatible_with_all_grid_brackets=proportional_lo<proportional_hi,
            proportional_slope_required_lower=proportional_lo,proportional_slope_required_upper=proportional_hi,
            caveat='Descriptive compatibility of observed grid brackets, not a population hypothesis test or an exact continuous-budget threshold.'))
    adjacent=[]
    for budget in [131328,262400]:
        vals={r:float(next(q for q in fixed if int(q['rank'])==r and q['method']=='truncated' and int(q['transitions'])==budget)['median_gap']) for r in ranks}
        for lo,hi in zip(ranks[:-1],ranks[1:]):
            adjacent.append(dict(transitions=budget,low_rank=lo,high_rank=hi,rank_ratio=hi/lo,
                median_gap_ratio=vals[hi]/vals[lo],adjacent_gap_slope=(vals[hi]-vals[lo])/(hi-lo)))
    doubling=[]
    for rank in ranks:
        lower=float(next(q for q in fixed if int(q['rank'])==rank and q['method']=='truncated' and int(q['transitions'])==131328)['median_gap'])
        higher=float(next(q for q in fixed if int(q['rank'])==rank and q['method']=='truncated' and int(q['transitions'])==262400)['median_gap'])
        doubling.append(dict(rank=rank,budget_ratio=262400/131328,median_gap_ratio=lower/higher,
            low_budget_times_gap=131328*lower,high_budget_times_gap=262400*higher))
    source={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.input.iterdir() if p.is_file()}
    result=dict(status='complete',sample_scaling_grid_compatibility=results,fixed_budget_adjacent_slopes=adjacent,
        budget_doubling_comparison=doubling,
        source_report=str(a.input),source_sha256=source,
        interpretation='Distinguish approximate affine scaling from strict proportionality to rank. Seed uncertainty is conditional on one fixed system and does not remove cross-rank control/exploration confounding.')
    (a.output/'additional_scaling_analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(results=results,adjacent=adjacent),indent=2))


if __name__=='__main__':main()
