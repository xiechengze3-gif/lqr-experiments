"""Static report syntax/global-dependency and frozen-statistics identity checks."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
checker_path = HERE.parent/'x10-20261106/prepare_ce_v2.py'
spec = importlib.util.spec_from_file_location('stdlib_global_checker', checker_path)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
names = ['render_report.py', 'transfer_report.py', 'audit_formal_x9.py',
         'copy_report_provenance.py', 'submit_report_x9.py', 'build_report_release.py']
results = []
for name in names:
    path = HERE/name
    text = path.read_text(encoding='utf-8')
    ast.parse(text, filename=name)
    unresolved = checker.global_name_audit(text, name)
    assert not unresolved, (name, unresolved)
    results.append(dict(file=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        AST='PASS', function_global_dependencies='RESOLVED'))
config = json.loads((HERE/'prepared-formal-v1/formal-config.json').read_text())
for name, digest in config['scientific_sources'].items():
    assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == digest
proof = dict(status='REPORT_STATIC_CHECKS_AND_FROZEN_SCIENCE_IDENTITY_PASS',
             files=results, frozen_scientific_sources_unchanged=True,
             numerical_execution=False, new_jobs=0, additional_SU=0)
with (HERE/'REPORT_STATIC_CHECKS_v1.json').open('x', encoding='utf-8') as stream:
    json.dump(proof, stream, indent=2)
    stream.write('\n')
print(json.dumps(dict(status=proof['status'], checked_files=len(results), numerical_execution=False)))
