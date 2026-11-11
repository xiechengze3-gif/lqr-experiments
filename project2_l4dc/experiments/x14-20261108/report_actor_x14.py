"""Read X14 archives and execute the frozen X9 endpoint and statistics loops."""
import argparse
import ast
import csv
import hashlib
import io
import json
import os
import tarfile
from pathlib import Path

import analyze_x9 as analysis
import x9_core as core
from run_actor_x14 import choose
from virtual_task_store_v2 import file_sha, verify_archive


ANALYZER_SHA = '7eafc31a73ab8e3f8924561d4892682e8bf73f57b06b5c321018494792a773bd'


def frozen_loop(function, target):
    source = Path(analysis.__file__)
    assert file_sha(source) == ANALYZER_SHA
    tree = ast.parse(source.read_bytes())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    candidates = node.body if function=='main' else ast.walk(node)
    loops = [n for n in candidates if isinstance(n, ast.For) and ast.unparse(n.target) == target]
    assert len(loops) == 1, (function, target, len(loops))
    return compile(ast.Module(body=loops, type_ignores=[]), str(source), 'exec')


def records(root, tag, config_path, config):
    end_loop = frozen_loop('saved_endpoints', 'arm')
    endpoints, stages = [], []
    task_count = len(config['new_alphas'])*64
    for i in range(task_count):
        alpha, algorithm, system, seed = choose(tag,'formal',i,config)
        prefix = f'x14{tag}-formal-{i:03d}'
        archive = root/(prefix+'.tar')
        journal = root/(prefix+'.jsonl')
        final = json.loads(journal.read_bytes().splitlines()[-1])
        assert final['status']=='COMPLETE' and final['kind']=='TASK_FINAL'
        assert (final['alpha'],final['algorithm'],final['system'],final['seed'],final['index'])==(alpha,algorithm,system,seed,i)
        assert final['config_sha256']==file_sha(config_path)
        assert final['archive_sha256']==file_sha(archive)
        verify_archive(archive,final['members'])
        assert [p['rung'] for p in final['paths']]==config['rungs']
        with tarfile.open(archive,'r:') as tf:
            for path, schedule in zip(final['paths'],config['all_schedules']):
                data = tf.extractfile(path['path']+'/DONE.json').read()
                assert hashlib.sha256(data).hexdigest()==path['done_sha256']
                raw = json.loads(data)
                assert raw['source_sha256']==file_sha(core.actor.__file__) and raw['engine_sha256']==file_sha(core.e.__file__)
                spec = raw['spec']
                assert (spec['system'],spec['seed'],spec['alpha'],spec['rung'],raw['algorithm'])==(system,seed,alpha,path['rung'],algorithm)
                expected = schedule['primitive_per_arm_per_algorithm']
                assert raw['primitive_transitions']==dict(dense=expected,truncated=expected)
                expected_stages = len(schedule['batches'][algorithm])
                assert len(raw['records'])==2*(expected_stages+1)
                env = dict(vars(analysis), raw=raw, expected=expected, expected_stages=expected_stages,
                           endpoints=endpoints, stages=stages)
                exec(end_loop,env)
    assert len(endpoints)==2*task_count*len(config['rungs'])
    assert len({tuple(r[k] for k in ('alpha','algorithm','rung','system','seed','arm')) for r in endpoints})==len(endpoints)
    return endpoints, stages


def csv_bytes(rows, schema):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer,fieldnames=schema)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def table_rows(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline='')))


def write(path, data):
    with path.open('xb') as f:
        f.write(data)


def main(a):
    core.e.require_compute()
    config_path = a.root/f'config-x14{a.item}-v1.json'
    config = json.loads(config_path.read_bytes())
    core.verify(config)
    endpoints, stages = records(a.root,a.item,config_path,config)
    env = dict(vars(analysis), config=config, endpoints=endpoints, summary=[], pairs=[])
    exec(frozen_loop('main','(algorithm, tag)'),env)
    summary = env['summary']
    inputs = Path(__file__).parent
    original = (inputs/'x9-summary.csv').read_bytes()
    original_rows = table_rows(original)
    schema = list(original_rows[0])
    assert len(summary)==len(config['new_alphas'])*len(config['rungs'])*4
    assert all(set(row)==set(schema) for row in summary)
    output = a.root/f'x14{a.item}-report'
    output.mkdir()
    summary_bytes = csv_bytes(summary,schema)
    write(output/'summary.csv',summary_bytes)
    # Preserve the field ordering of X9 tables while selecting X14's new rows.
    for name, rows in [('endpoints',endpoints),('new_stages',stages),('new_paired_endpoints',env['pairs']),
                       ('failures',[row for row in endpoints if not row['stable']])]:
        with (inputs/f'x9-{name}-header.csv').open(newline='',encoding='utf-8-sig') as f:
            fields = next(csv.reader(f))
        write(output/(name+'.csv'),csv_bytes(rows,fields))
    derived_input = summary
    if a.item=='b':
        alpha_zero = table_rows((inputs/'x10-n24-summary.csv').read_bytes())
        alpha_zero = [dict(row,alpha='0.0',tau2_sq='0.0') for row in alpha_zero]
        assert len(alpha_zero)==36 and all(set(r)==set(schema) for r in alpha_zero)
        by = {(r['algorithm'],float(r['rung']),r['ratio_kind']):r for r in alpha_zero}
        for row in original_rows:
            if float(row['alpha'])==0:
                ref = by.pop((row['algorithm'],float(row['rung']),row['ratio_kind']))
                assert row==ref, (row,ref)
        assert len(by)==20
        a_rows = table_rows((a.root/'x14a-report/summary.csv').read_bytes())
        assert len(a_rows)==36
        added = [*by.values(),*summary,*a_rows]
        merged = original+csv_bytes(added,schema).split(b'\n',1)[1]
        assert len(table_rows(merged))==216
        write(output/'X9_summary_merged_nine_rungs.csv',merged)
        derived_input = table_rows(merged)
    alphas = sorted({float(row['alpha']) for row in derived_input})
    env.update(config=dict(config,alphas=alphas), summary=derived_input, derived=[])
    exec(frozen_loop('main','alpha'),env)
    derived = env['derived']
    write(output/('X9_transitions_saved_merged_nine_rungs.csv' if a.item=='b' else 'transitions_saved_derived.csv'),
          csv_bytes(derived,list(derived[0])))
    receipt = dict(status='COMPLETE_SAVED_DATA_REPORT', item=a.item, job=os.environ['SLURM_JOB_ID'],
                   source_sha256=file_sha(__file__), frozen_analyzer_sha256=ANALYZER_SHA,
                   new_endpoints=len(endpoints), new_stages=len(stages), new_summary_rows=len(summary),
                   new_observation_transitions=0, files={p.name:file_sha(p) for p in sorted(output.iterdir())})
    write(output/'REPORT_DONE.json',(json.dumps(receipt,indent=2)+'\n').encode())
    print(json.dumps(receipt))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('item',choices=['a','b'])
    parser.add_argument('--root',type=Path,required=True)
    main(parser.parse_args())
