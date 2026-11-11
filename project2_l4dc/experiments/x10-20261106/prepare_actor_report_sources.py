"""Adapt only the coverage assertion for five registered new rungs."""
import ast
import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    original = HERE/'actor-draft-v2/analyze_actor.py'
    data = original.read_bytes()
    text = data.decode()
    frozen = json.loads((HERE/'actor-draft-v2/actor-config-protocol-v1.json').read_text())
    assert sha(data) == frozen['scientific_sources']['analyze_actor.py']
    old = '    assert len(ends)==4*2*32*2 and len(stages)==4*32*(2*17+2*9)'
    new = '    assert len(ends)==len(config[\'rungs\'])*2*32*2 and len(stages)==len(config[\'rungs\'])*32*(2*17+2*9)'
    assert text.count(old) == 1
    changed = text.replace(old, new)
    assert changed.replace(new, old) == text
    tree_before, tree_after = ast.parse(text), ast.parse(changed)
    functions_before = {n.name:ast.get_source_segment(text,n) for n in tree_before.body if isinstance(n,ast.FunctionDef)}
    functions_after = {n.name:ast.get_source_segment(changed,n) for n in tree_after.body if isinstance(n,ast.FunctionDef)}
    assert set(functions_before) == set(functions_after)
    unchanged = []
    for name in functions_before:
        if name == 'inspect':
            assert functions_after[name].replace(new.strip(),old.strip()) == functions_before[name]
        else:
            assert functions_before[name] == functions_after[name], name
            unchanged.append(name)
    destination = HERE/'actor-report-src-v1'
    assert not destination.exists()
    destination.mkdir()
    with (destination/'analyze_actor_five_rungs.py').open('xb') as stream:
        stream.write(changed.encode())
    proof = dict(status='PASS_COVERAGE_ASSERTION_ONLY', created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 original_path=str(original), original_sha256=sha(data), new_sha256=sha(changed.encode()),
                 literal_reversible_replacement=True, only_changed_function='inspect',
                 changed_assertion_before=old.strip(), changed_assertion_after=new.strip(),
                 statistics_and_other_functions_byte_identical=unchanged,
                 expected_endpoints_per_dimension=5*2*32*2, expected_stages_per_dimension=5*32*(2*17+2*9),
                 numerical_work=0, new_jobs=0, SU=0)
    with (destination/'COVERAGE_SOURCE_PROOF_v1.json').open('x') as stream:
        json.dump(proof,stream,indent=2)
    print(json.dumps(proof))


if __name__ == '__main__':
    main()
