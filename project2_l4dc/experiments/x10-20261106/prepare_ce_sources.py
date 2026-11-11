"""Copy/extract original CE numerical functions without importing science locally."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def function(path, name):
    text = path.read_text(encoding='utf-8')
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(text, node)


def main():
    engine_path = EXP/'x6-20261101/X6b-protocol-v2/frozen_engine.py'
    estimator_path = EXP/'x6-20261101/X6b-protocol-v2/estimation.py'
    x8_path = EXP/'x8-local-20261104/run_x8.py'
    engine = engine_path.read_bytes()
    estimator = estimator_path.read_bytes()
    assert sha(engine) == '9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989'
    assert sha(estimator) == 'f587bd48993288dbf9160dd4cc1e62542f15ee5794bda37590ec48dc672c9c59'
    new(HERE/'ce-src/frozen_engine.py', engine)
    new(HERE/'ce-src/x8_original.py', x8_path.read_bytes())
    # Original estimation.py imports Unix resource at module level. Extract only
    # its two unchanged numerical functions so native Windows needs no fake module.
    s_functions = {name: function(estimator_path, name) for name in ['model', 'ce_prefixes']}
    s_module = ('"""Unchanged frozen S-model and CE-prefix functions; portable imports only."""\n'
                'import numpy as np\n'
                'from scipy.linalg import solve_discrete_are, solve_discrete_lyapunov\n'
                'import frozen_engine as e\n\n'+'\n\n'.join(s_functions.values())+'\n')
    new(HERE/'ce-src/s_ce_original.py', s_module.encode())
    for name in s_functions:
        assert function(HERE/'ce-src/s_ce_original.py', name) == s_functions[name]
    # Validation reference: preserve every numerical statement and replace only
    # the required Slurm provenance read. No fake Slurm job id or compute guard.
    original = function(engine_path, 'ce_run')
    marker = "job=os.environ['SLURM_JOB_ID']"
    assert original.count(marker) == 1
    portable = original.replace(marker, "job=None,execution_context='LOCAL_AUTHOR_APPROVED_X10'")
    assert portable.replace("job=None,execution_context='LOCAL_AUTHOR_APPROVED_X10'", marker) == original
    reference_module = ('"""Pilot-only original ce_run with explicit local provenance."""\n'
                        'import time, math\nimport numpy as np\n'
                        'from frozen_engine import rng, ce_chunk, fit_model, ce_learner, assess, sha, save\n\n'
                        +portable+'\n')
    new(HERE/'ce-src/ce_reference_local.py', reference_module.encode())
    files = list((HERE/'ce-src').glob('*.py'))
    for path in files:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    proof = dict(status='ORIGINAL_CE_SOURCES_PREPARED_NO_IMPORT_OR_EXECUTION',
                 files={p.name: sha(p.read_bytes()) for p in files},
                 source_references=[dict(path=str(p), sha256=sha(p.read_bytes()))
                                    for p in [engine_path, estimator_path, x8_path]],
                 s_function_extractions='model and ce_prefixes source text exactly identical',
                 reference_change='Only Slurm job provenance read replaced with explicit local execution descriptor',
                 new_simulations=0, new_jobs=0, Grace_SU=0)
    new(HERE/'CE_SOURCE_PREPARATION_v1.json', (json.dumps(proof, indent=2)+'\n').encode())
    print(json.dumps(proof))


if __name__ == '__main__':
    main()
