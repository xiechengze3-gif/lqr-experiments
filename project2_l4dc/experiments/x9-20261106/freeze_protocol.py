"""Stdlib-only source freeze, immutable package and append-only protocol delivery."""
import ast
import datetime
import hashlib
import io
import json
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL = HERE.parents[1]
OLD = HERE.parent/'x6-20261101/X6b-protocol-v2'
GO_SHA = 'fa9c096667a147ed70a135eb9fcc415e9e6e00f3e71f0c0957f00f825352201a'
GO_HEADING = '## X9 GO (22:35 CDT 11/05)'
NAME = 'x9-20261106-resource-v1'


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def new(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(payload)


def js(obj):
    return (json.dumps(obj, indent=2)+'\n').encode()


def main():
    review = (CHANNEL/'CLAUDE_TASK.md').read_bytes()
    assert sha(review) == GO_SHA and GO_HEADING.encode() in review
    prior = (CHANNEL/'CODEX_REPLY.md').read_bytes()
    assert b'## X9 PROTOCOL' not in prior
    cfg = json.loads((OLD/'prepared-formal-v1/formal-config.json').read_text())
    assert cfg['scientific_sources']['frozen_engine.py'] == sha((OLD/'frozen_engine.py').read_bytes())
    for name in ['frozen_engine.py', 'estimation.py']:
        new(HERE/name, (OLD/name).read_bytes())
    actor = (OLD/'actor_paths.py').read_bytes()
    assert sha(actor) == cfg['scientific_sources']['actor_paths.py']
    old_root = b'/scratch/user/changze/lqr_experiments/results/x6-20261101/X6b'
    new_root = b'/scratch/user/changze/lqr_experiments/results/x9-20261106'
    assert actor.count(old_root) == 1
    adapted = actor.replace(old_root, new_root)
    assert adapted.replace(new_root, old_root) == actor
    new(HERE/'actor_paths.py', adapted)
    new(HERE/'baseline/formal-config.json', (OLD/'prepared-formal-v1/formal-config.json').read_bytes())
    baseline_models = {}
    for system in cfg['formal_systems']:
        meta = cfg['model_registry'][f'n24-s{system}']
        source = OLD/'prepared-formal-v1'/meta['path']
        payload = source.read_bytes()
        assert sha(payload) == meta['sha256']
        name = f'baseline/models/n24-s{system}.npz'
        new(HERE/name, payload)
        baseline_models[str(system)] = dict(meta, path=name)
    for name in ['summary.csv', 'endpoints.csv']:
        new(HERE/'baseline'/name, (OLD.parent/'X6b-report-v1'/name).read_bytes())
    for name in ['x6b_reuse_identity_v1.json', 'APPEND_RECEIPT_v1.json']:
        new(HERE/'baseline'/name, (HERE.parent/'x9-query-20261106'/name).read_bytes())
    figure_source = Path('C:/Users/24375/Projects/project2_l4dc/figs/make_figs.py')
    tree = ast.parse(figure_source.read_text(encoding='utf-8'))
    cross = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'cross')
    new(HERE/'baseline/paper_cross_readonly.py',
        ('# Read-only source excerpt, not imported/executed locally.\n'+ast.get_source_segment(figure_source.read_text(encoding='utf-8'), cross)+'\n').encode())
    new(HERE/'CLAUDE_TASK_GO.md', review)
    names = ['frozen_engine.py', 'estimation.py', 'actor_paths.py', 'x9_core.py', 'analyze_x9.py']
    for name in names+['remote_x9.py', 'freeze_protocol.py']:
        ast.parse((HERE/name).read_text(encoding='utf-8'), filename=name)
    scientific = {name: sha((HERE/name).read_bytes()) for name in names}
    sources = {p.relative_to(HERE).as_posix(): sha(p.read_bytes())
               for p in (HERE/'baseline').rglob('*') if p.is_file()}
    cases = [dict(alpha=.05, algorithm='NPG', system=9601, seed=1901, prepare_alpha=.05),
             dict(alpha=.05, algorithm='PI', system=9601, seed=1901, prepare_alpha=.1),
             dict(alpha=.4, algorithm='NPG', system=9602, seed=1902, prepare_alpha=.2),
             dict(alpha=.4, algorithm='PI', system=9602, seed=1902, prepare_alpha=.4)]
    groups = []
    for alpha in [.05, .1, .2, .4]:
        for old in [g for g in cfg['formal_groups'] if g['n'] == 24]:
            groups.append(dict(old, id=f'a{alpha}-'+old['id'], alpha=alpha))
    schedules = [x for x in cfg['all_schedules'] if x['n'] == 24]
    assert sum(s['primitive_per_arm_per_algorithm'] for s in schedules)*128*4 == 128849584128
    config = dict(experiment='X9', version=1, status='PROTOCOL_FROZEN', family='S',
                  n_values=[24], rank=2, alphas=[0., .05, .1, .2, .4],
                  new_alphas=[.05, .1, .2, .4], cap_SU=50, eta=.2, H=16, nu=1.,
                  burn_blocks=16, baseline_blocks=1, selected_NPG_T=16, selected_PI_T=8,
                  formal_systems=cfg['formal_systems'], formal_sampling_seeds=cfg['formal_sampling_seeds'],
                  pilot_systems=[9601, 9602], pilot_cases=cases, all_schedules=schedules,
                  rungs=cfg['rungs'], formal_groups=groups,
                  baseline_models=baseline_models, scientific_sources=scientific, baseline_sources=sources,
                  bootstrap_tag=cfg['bootstrap_tag'], bootstrap_repetitions=5000,
                  author_go_sha256=GO_SHA, formal_requires='PILOT ACCEPTED')
    assert len(groups) == 12
    new(HERE/'config-protocol-v1.json', js(config))
    protocol = (HERE/'PROTOCOL_PLAN.md').read_bytes()+b'\n\n## Frozen hashes\n\n'
    protocol += ('Config SHA256: '+sha((HERE/'config-protocol-v1.json').read_bytes())+'\n\n').encode()
    protocol += ''.join(f'- {name}: {digest}\n' for name, digest in scientific.items()).encode()
    protocol += ('\nSource AST, byte-identity and scalar count checks PASS; numerical equivalence/RSS/timing PENDING compute pilot.\n'
                 'Prepared before any X9 numerical work. X9 requested 0/50 SU, settled 0 SU.\n').encode()
    new(HERE/'PROTOCOL_v1.md', protocol)
    approval = dict(experiment='X9', stage='PILOT', exact_go_heading=GO_HEADING,
                    review_sha256=GO_SHA, protocol_sha256=sha(protocol))
    new(HERE/'approval.json', js(approval))
    shell = '''#!/usr/bin/env bash
set -euo pipefail
base=/scratch/user/changze/lqr_experiments
release=$base/releases/x9-20261106-resource-v1
cache=$base/cache/x9-20261106
temp=$base/tmp/x9-20261106/job-${SLURM_ARRAY_JOB_ID:?}-${SLURM_ARRAY_TASK_ID:?}
mkdir -p "$cache/numba" "$cache/matplotlib" "$temp"
export TMPDIR="$temp" TEMP="$temp" TMP="$temp" XDG_CACHE_HOME="$cache"
export NUMBA_CACHE_DIR="$cache/numba" MPLCONFIGDIR="$cache/matplotlib"
export LQR_NUMBA_SITE=/sw/eb/sw/Anaconda3/2024.02-1/lib/python3.11/site-packages
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1
cd "$release"
sha256sum -c SHA256SUMS >/dev/null
/scratch/user/changze/healthcare_project1_2/envs/t1d-robust-py311-v1/bin/python -B x9_core.py resource --config config-protocol-v1.json --index "$SLURM_ARRAY_TASK_ID"
'''
    new(HERE/'run.sbatch', shell.encode())
    package_names = names+['remote_x9.py', 'config-protocol-v1.json', 'PROTOCOL_v1.md',
                            'approval.json', 'CLAUDE_TASK_GO.md', 'run.sbatch']+list(sources)
    hashes = {name: sha((HERE/name).read_bytes()) for name in package_names}
    sums = ''.join(f'{digest}  {name}\n' for name, digest in hashes.items()).encode()
    new(HERE/'SHA256SUMS', sums)
    package_names.append('SHA256SUMS')
    package = HERE/'packages'/(NAME+'.tar.gz')
    package.parent.mkdir(exist_ok=True)
    assert not package.exists()
    with tarfile.open(package, 'x:gz') as tf:
        for name in package_names:
            payload = (HERE/name).read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    manifest = dict(status='PROTOCOL_FROZEN_PILOT_AUTHORIZED_BY_GO',
                    created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    review_sha256=GO_SHA, config_sha256=sha((HERE/'config-protocol-v1.json').read_bytes()),
                    sha256sums_sha256=sha(sums), files=hashes,
                    archive=str(package), archive_sha256=sha(package.read_bytes()),
                    actor_difference='Only the single allowed-output-root string; reverse replacement is byte-identical.',
                    paper_figure_source_sha256=sha(figure_source.read_bytes()),
                    no_scientific_execution_yet=True, requested_SU=0, settled_SU=0,
                    cap_SU=50, proposed_requested_total_SU=49.93333333333334)
    new(HERE/'PROTOCOL_MANIFEST_v1.json', js(manifest))
    section = ('\n\n## X9 PROTOCOL\n\n'+protocol.decode().split('\n', 1)[1].lstrip()
               +'\nDelivery: `experiments/x9-20261106/PROTOCOL_v1.md`, config, wrappers, baseline reference files, '
               'frozen saved-record analysis, SHA256SUMS and `PROTOCOL_MANIFEST_v1.json`.\n'
               'Config SHA256 `'+manifest['config_sha256']+'`; SHA256SUMS SHA256 `'+sha(sums)+'`.\n'
               'Alpha0 identity/reuse is the accepted X9 QUERY audit; no old file changed. '
               'Full protocol, exact integer schedules and source hashes are available for review. '
               'The explicit X9 GO order authorizes the four-job resource/equivalence pilot after this delivery; '
               'FORMAL will wait for your PILOT ACCEPTED. X9 requested/settled 0/0 SU of50; no job submitted yet.\n\n'
               'STATUS: PROTOCOL DONE X9\n').encode()
    assert (CHANNEL/'CLAUDE_TASK.md').read_bytes() == review
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes() == prior
    with (CHANNEL/'CODEX_REPLY.md').open('ab') as stream:
        stream.write(section)
    assert (CHANNEL/'CODEX_REPLY.md').read_bytes() == prior+section
    new(HERE/'PROTOCOL_APPEND_RECEIPT_v1.json', js(dict(
        prior_reply_bytes=len(prior), prior_reply_sha256=sha(prior), appended_bytes=len(section),
        appended_sha256=sha(section), prior_prefix_preserved=True, review_sha256=GO_SHA)))
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}))


if __name__ == '__main__':
    main()
