"""Assemble and verify the nine-rung X9/X14 delivery from sealed CSVs."""
import csv
import hashlib
import io
import json
import math
from collections import Counter
from pathlib import Path


R=Path(__file__).resolve().parent
X9=R.parent/'x9-20261106'
X10=R.parent/'x10-20261106/delivery-actor-report-v1/report-v1/new-rungs'
X6=R.parent/'x6-20261101/X6b-report-v1'
A=R/'delivery-a-report'
B=R/'delivery-b-report'
ALPHAS=(0.,.02,.05,.1,.2,.4)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def verified(directory, filename, receipt='verification.json'):
    path=directory/filename
    data=path.read_bytes()
    expected=read(directory/receipt)['files'][filename]
    assert digest(data)==expected,path
    return data


def records(data):
    reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline=''))
    result=list(reader)
    assert all(None not in row and None not in row.values() for row in result)
    return reader.fieldnames,result


def write(path,data):
    with path.open('xb') as f:
        f.write(data)


def csv_data(fields,rows):
    output=io.StringIO(newline='')
    writer=csv.DictWriter(output,fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode('utf-8')


def key(row):
    return (float(row['alpha']),row['algorithm'],float(row['rung']),int(float(row['system'])),
            int(float(row['seed'])),row['arm'])


def stage(row):
    return int(float(row['stage']))


def rank_two(rows,origin):
    return [dict(r,alpha='0.0',tau2_sq='0.0',origin=origin,m='24',r='2',physical_rank='2')
            for r in rows if float(r['n'])==24]


def table(directory,name):
    return records(verified(directory,name,'REPORT_DONE.json'))


def merge():
    x9=X9/'delivery-report-v1/report-v1'
    summary_name='X9_summary_merged_nine_rungs.csv'
    crossing_name='X9_transitions_saved_merged_nine_rungs.csv'
    summary=verified(B,summary_name,'REPORT_DONE.json')
    assert summary.startswith((X9/'summary.csv').read_bytes())
    _,metrics=records(summary)
    _,cross=table(B,crossing_name)
    assert len(cross)==12
    endpoint_fields,old=records(verified(x9,'endpoints.csv'))
    failure_fields,old_fail=records(verified(x9,'failures.csv'))
    assert endpoint_fields==failure_fields
    assert {key(r) for r in old_fail}=={key(r) for r in old if r['stable']=='False'}
    stage_fields,old_stages=records(verified(x9,'new_stages.csv'))
    _,extra=records(verified(X10,'endpoints.csv'))
    _,extra_stages=records(verified(X10,'stages.csv'))
    _,original_rank_two_stages=records(verified(X6,'stages.csv'))
    endpoints=old+rank_two(extra,'REUSED_X10b_N24_EXTRA_RUNG')
    stages=old_stages+rank_two(original_rank_two_stages,'')+rank_two(extra_stages,'')
    for folder in (A,B):
        ef,extra_end=table(folder,'endpoints.csv')
        sf,extra_stage=table(folder,'new_stages.csv')
        ff,failed=table(folder,'failures.csv')
        assert ef==ff==endpoint_fields and sf==stage_fields
        assert {key(r) for r in failed}=={key(r) for r in extra_end if r['stable']=='False'}
        endpoints.extend(extra_end)
        stages.extend(extra_stage)
    end_by={key(r):r for r in endpoints}
    assert len(end_by)==len(endpoints)==6912
    seen=Counter((key(r),stage(r)) for r in stages)
    assert len(seen)==len(stages)==89856 and set(seen.values())=={1}
    assert {k for k,t in seen}==set(end_by)
    for k,row in end_by.items():
        assert stage(row)=={'PI':8,'NPG':16}[k[1]]
        assert all((k,t) in seen for t in range(stage(row)+1))
    stable=Counter()
    for k,row in end_by.items():
        assert row['stable'] in ('True','False')
        assert math.isfinite(float(row['gap']))==(row['stable']=='True')
        stable[k[:3]+(k[-1],)]+=row['stable']=='True'
    assert len(metrics)==216
    for row in metrics:
        cell=(float(row['alpha']),row['algorithm'],float(row['rung']))
        assert int(row['dense_stable'])==stable[cell+('dense',)]
        assert int(row['truncated_stable'])==stable[cell+('truncated',)]
    failures=[r for r in endpoints if r['stable']=='False']
    output={summary_name:summary,crossing_name:verified(B,crossing_name,'REPORT_DONE.json'),
            'endpoints.csv':csv_data(endpoint_fields,[{k:r.get(k,'') for k in endpoint_fields} for r in endpoints]),
            'stages.csv':csv_data(stage_fields,[{k:r.get(k,'') for k in stage_fields} for r in stages]),
            'failures.csv':csv_data(failure_fields,[{k:r.get(k,'') for k in failure_fields} for r in failures])}
    assert not any((R/name).exists() for name in [*output,'ACTOR_DELIVERY_v1.json'])
    for name,data in output.items():
        write(R/name,data)
    proof=dict(status='COMPLETE_ALL_ACTOR_CELLS',summary_rows=216,endpoint_rows=len(endpoints),
               stage_rows=len(stages),failure_rows=len(failures),x9_summary_exact_prefix=True,
               baseline_stage_fields='Available X6b/X10b fields retained; unknown X9 fields left empty.',
               files={name:digest(data) for name,data in output.items()})
    write(R/'ACTOR_DELIVERY_v1.json',(json.dumps(proof,indent=2)+'\n').encode())
    print(json.dumps(proof))


if __name__=='__main__':
    merge()
