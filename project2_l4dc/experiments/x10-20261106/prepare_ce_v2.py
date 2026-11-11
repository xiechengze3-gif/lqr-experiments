"""Prepare a reviewable import-only CE correction, never run/retry a pilot."""
import ast
import builtins
import hashlib
import json
import symtable
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def extract(text, name):
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(text, node)


def global_name_audit(text, filename):
    tree = ast.parse(text)
    defined = set(dir(builtins)) | {'__file__', '__name__'}
    for node in tree.body:
        if isinstance(node, ast.Import):
            defined.update(a.asname or a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            defined.update(a.asname or a.name for a in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            defined.update(n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name))
    missing = set()
    def visit(table):
        for symbol in table.get_symbols():
            if symbol.is_global() and symbol.is_referenced() and symbol.get_name() not in defined:
                missing.add(symbol.get_name())
        for child in table.get_children():
            visit(child)
    # Function scopes only; main-guard variables and comprehension locals are not imports.
    table = symtable.symtable(text, filename, 'exec')
    for child in table.get_children():
        visit(child)
    return sorted(missing)


def main():
    old = HERE/'ce-src'
    target = HERE/'ce-src-v2'
    assert not target.exists()
    old_s = (old/'s_ce_original.py').read_text(encoding='utf-8')
    assert global_name_audit(old_s, 's_ce_original.py') == ['json']
    for path in old.glob('*.py'):
        text = path.read_text(encoding='utf-8')
        if path.name == 's_ce_original.py':
            text = text.replace('import numpy as np\n', 'import json\nimport numpy as np\n', 1)
            for name in ['model', 'ce_prefixes']:
                assert extract(text, name) == extract(old_s, name)
        elif path.name == 'ce_driver.py':
            before = text
            text = text.replace('ce-pilot-v1', 'ce-pilot-v2').replace('ce-formal-v1', 'ce-formal-v2')
            text = text.replace('ce-config-protocol-v1.json', 'ce-config-protocol-v2.json')
            call = "x = run_x8(dict(family='geometric', config='rho0.85', rho=.85), 9901, 7701, dest/'x8')"
            assert text.count(call) == 1
            reuse = ("old_x8_path = ROOT/'ce-pilot-v1/x8/DONE.json'\n"
                     "    x = json.loads(old_x8_path.read_text())\n"
                     "    assert x['status'] == 'COMPLETE'\n"
                     "    assert x['original_source_sha256'] == sha(Path(x8.__file__))\n"
                     "    assert x['spec'] == dict(family='geometric', config='rho0.85', rho=.85, system=9901, seed=7701)\n"
                     "    assert x['primitive_transitions'] == 262656 and len(x['records']) == 480\n"
                     "    assert x['wrapper_sha256'] == sha(ROOT/'ce-src/ce_driver.py')\n"
                     "    # Complete unchanged X8 pilot reused by reference, never sampled again.")
            text = text.replace(call, reuse)
            assert extract(text, 'run_x8') == extract(before, 'run_x8')
            assert extract(text, 'run_shared_ce') == extract(before, 'run_shared_ce')
            assert extract(text, 'equivalence') == extract(before, 'equivalence')
        elif path.name == 'analyze_ce.py':
            text = text.replace('ce-formal-v1', 'ce-formal-v2').replace('ce-report-v1', 'ce-report-v2')
        missing = global_name_audit(text, path.name) if path.name in ['s_ce_original.py', 'ce_reference_local.py'] else []
        assert not missing, (path.name, missing)
        ast.parse(text, filename=path.name)
        new(target/path.name, text.encode())
    launcher = (HERE/'Launch-CE-v2.ps1').read_text()
    launcher = launcher.replace('ce-config-protocol-v1.json', 'ce-config-protocol-v2.json')
    launcher = launcher.replace('ce-pilot-v1', 'ce-pilot-v2').replace('ce-formal-v1', 'ce-formal-v2').replace('ce-report-v1', 'ce-report-v2')
    launcher = launcher.replace('ce-src\\', 'ce-src-v2\\')
    new(HERE/'Launch-CE-v3.ps1', launcher.encode())
    config = json.loads((HERE/'ce-config-protocol-v1.json').read_text())
    config['status'] = 'PROTOCOL_V2_PREPARED_WAITING_REVIEW_NO_RETRY'
    config['version'] = 2
    config['sources'] = {key: value for key, value in config['sources'].items() if not key.startswith('ce-src/')}
    config['sources'].update({p.relative_to(HERE).as_posix(): sha(p.read_bytes()) for p in target.glob('*.py')})
    config['reused_pilot_X8'] = dict(path='ce-pilot-v1/x8/DONE.json',
                                    sha256=sha((HERE/'ce-pilot-v1/x8/DONE.json').read_bytes()))
    new(HERE/'ce-config-protocol-v2.json', (json.dumps(config, indent=2)+'\n').encode())
    proof = dict(status='CORRECTION_PREPARED_NO_NUMERICAL_RETRY',
                 missing_import_fixed='json in portable extraction module',
                 numerical_function_sources_unchanged=True,
                 original_model_prefix_function_globals_resolved=True,
                 original_reference_function_globals_resolved=True,
                 complete_X8_pilot_reused_by_reference=True,
                 incomplete_v1_files_preserved=True, new_jobs=0, new_SU=0,
                 config_sha256=sha((HERE/'ce-config-protocol-v2.json').read_bytes()),
                 files={p.relative_to(HERE).as_posix(): sha(p.read_bytes()) for p in target.glob('*.py')})
    new(HERE/'CE_IMPORT_CORRECTION_v2.json', (json.dumps(proof, indent=2)+'\n').encode())
    print(json.dumps({k: v for k, v in proof.items() if k != 'files'}))


if __name__ == '__main__':
    main()
