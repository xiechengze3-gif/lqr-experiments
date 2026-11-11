"""X10b source/count preparation only. Resource authorization remains pending."""
import ast
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent/'x6-20261101/X6b-protocol-v2'
DEST = HERE/'actor-draft-v2'
OLD_ROOT = '/scratch/user/changze/lqr_experiments/results/x6-20261101/X6b'
NEW_ROOT = '/scratch/user/changze/lqr_experiments/results/x10-20261106/X10b'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def main():
    assert not DEST.exists()
    cfg = json.loads((OLD/'prepared-formal-v1/formal-config.json').read_text())
    for name, digest in cfg['scientific_sources'].items():
        assert sha((OLD/name).read_bytes()) == digest
    adaptations = []
    for name in ['frozen_engine.py', 'estimation.py', 'actor_paths.py', 'formal_driver.py',
                 'analyze_actor.py', 'plot_saved_actor.py']:
        original = (OLD/name).read_text(encoding='utf-8')
        adapted = original
        if name in ['actor_paths.py', 'formal_driver.py', 'analyze_actor.py']:
            count = adapted.count(OLD_ROOT)
            assert count == 1, (name, count)
            adapted = adapted.replace(OLD_ROOT, NEW_ROOT)
        if name == 'formal_driver.py':
            assert adapted.count("experiment='X6b'") == 1
            adapted = adapted.replace("experiment='X6b'", "experiment='X10b'")
        reverse = adapted.replace(NEW_ROOT, OLD_ROOT)
        if name == 'formal_driver.py':
            reverse = reverse.replace("experiment='X10b'", "experiment='X6b'")
        assert reverse == original
        ast.parse(adapted, filename=name)
        # Preserve original bytes for entirely unchanged files.
        payload = (OLD/name).read_bytes() if adapted == original else adapted.encode()
        new(DEST/name, payload)
        adaptations.append(dict(file=name, original_sha256=sha((OLD/name).read_bytes()),
                                adapted_sha256=sha(payload),
                                change='None' if adapted == original else 'Output namespace and formal experiment descriptor only'))
    text = (OLD/'actor_paths.py').read_text()
    function = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == 'schedules')
    scalar = ast.get_source_segment(text, function)
    namespace = {'math': math}
    exec(compile(scalar, '<frozen-scalar-schedule>', 'exec'), namespace)
    new_rungs = [1/256, 1/128, 1/32, 1/8, 1/2]
    entries = []
    groups = []
    registry = {}
    for n in sorted(cfg['n_values'], reverse=True):
        for rung in new_rungs:
            batches = namespace['schedules'](cfg['npg_bases'][str(n)], rung, 16, 8)
            count = 16*(sum(batches['NPG'])+17*16)
            assert count == 16*(sum(batches['PI'])+17*8)
            entries.append(dict(n=n, rung=rung, batches=batches,
                                primitive_per_arm_per_algorithm=count))
        for alg in ['NPG', 'PI']:
            groups.append(dict(id=f'n{n}-new-five-{alg}', n=n,
                               runs=[dict(algorithm=alg, rung=r, rung_label='r'+str(r).replace('.', ''))
                                     for r in new_rungs], tasks=32, cpus=1, memory_MiB=2048,
                               status='RESOURCE_LIMIT_UNRESOLVED_NO_SUBMISSION'))
        for system in cfg['formal_systems']:
            key = f'n{n}-s{system}'
            meta = cfg['model_registry'][key]
            data = (OLD/'prepared-formal-v1'/meta['path']).read_bytes()
            assert sha(data) == meta['sha256']
            path = f'baseline/models/{key}.npz'
            new(DEST/path, data)
            registry[key] = dict(meta, path=path)
    for name in ['summary.csv', 'endpoints.csv']:
        new(DEST/'baseline'/name, (OLD.parent/'X6b-report-v1'/name).read_bytes())
    new(DEST/'baseline/X6b-formal-config.json', (OLD/'prepared-formal-v1/formal-config.json').read_bytes())
    original_replay = []
    for algorithm in ['NPG', 'PI']:
        relative = f'formal-v1/n24-low-three/task-0/{algorithm}-r0015625/DONE.json'
        path = OLD/'deliveries/formal-v1/X6b'/relative
        raw = json.loads(path.read_text())
        assert raw['spec']['system'] == 301 and raw['spec']['seed'] == 1701
        assert raw['spec']['rung'] == 1/64
        original_replay.append(dict(algorithm=algorithm, remote_path=OLD_ROOT+'/'+relative,
                                    sha256=sha(path.read_bytes()), spec=raw['spec']))
    base_keys = ['family', 'eta', 'nu', 'H', 'burn_blocks', 'baseline_blocks', 'formal_systems',
                 'formal_sampling_seeds', 'selected_NPG_T', 'selected_PI_T', 'npg_bases',
                 'bootstrap_tag', 'bootstrap_repetitions', 'required_successes', 'relative_epsilons']
    draft = {key: cfg[key] for key in base_keys}
    draft.update(experiment='X10b', status='DRAFT_RESOURCE_AUTHORIZED_PROTOCOL_NOT_YET_FROZEN',
                 n_values=sorted(cfg['n_values'], reverse=True), rank=2, rungs=new_rungs, all_schedules=entries,
                 formal_groups=groups, model_registry=registry, actual_forecast_cap_SU=160, requested_upper_cap_SU=200,
                 global_concurrency=8, automatic_retries=0,
                 original_replay=original_replay, resource_system=9102, resource_seed=9801,
                 frozen_scientific_sources={name: sha((DEST/name).read_bytes()) for name in
                     ['frozen_engine.py', 'actor_paths.py', 'formal_driver.py', 'analyze_actor.py', 'plot_saved_actor.py']},
                 new_formal_paired_paths=4*2*5*32,
                 new_formal_primitive_transitions=sum(e['primitive_per_arm_per_algorithm']*128 for e in entries),
                 resource_proposal_requested_SU=4+1/6,
                 resource_proposal_status='AUTHORIZED_BY_X10_DECISIONS_DF87773E_NO_JOBS_UNTIL_PROTOCOL_FROZEN')
    new(DEST/'actor-config-draft-v2.json', (json.dumps(draft, indent=2)+'\n').encode())
    proof = dict(status=draft['status'], adaptations=adaptations, copied_models=len(registry),
                 scalar_schedules=len(entries), new_formal_paired_paths=draft['new_formal_paired_paths'],
                 new_formal_primitive_transitions=draft['new_formal_primitive_transitions'],
                 no_new_model_solve=True, no_new_sampling=True, no_job=True, additional_SU=0)
    new(HERE/'ACTOR_DRAFT_SOURCE_PROOF_v2.json', (json.dumps(proof, indent=2)+'\n').encode())
    print(json.dumps({k: v for k, v in proof.items() if k != 'adaptations'}))


if __name__ == '__main__':
    main()
