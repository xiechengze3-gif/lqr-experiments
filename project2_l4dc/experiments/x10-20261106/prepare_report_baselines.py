"""Capture read-only paper CSV/cross references; never import or edit the paper."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER = Path('C:/Users/24375/Projects/project2_l4dc/figs')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    source_path = PAPER/'make_figs.py'
    source = source_path.read_bytes()
    text = source.decode()
    node = next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name == 'cross')
    function = ast.get_source_segment(text,node)
    reference_path = PAPER/'data/X6b_transitions_saved_derived.csv'
    reference = reference_path.read_bytes()
    destination = HERE/'actor-report-baseline-v1'
    assert not destination.exists()
    destination.mkdir()
    content = {'paper_cross.py':('"""Verbatim paper cross function; read-only reference extraction."""\nimport numpy as np\n\n'+function+'\n').encode(),
               'X6b_transitions_saved_derived.csv':reference}
    for name,data in content.items():
        with (destination/name).open('xb') as stream:stream.write(data)
    proof = dict(status='READ_ONLY_PAPER_REFERENCES_FROZEN_NO_COMPUTE',
                 paper_source_path=str(source_path), paper_source_sha256=sha(source),
                 cross_source_exact_text=True, cross_text_sha256=sha(function.encode()),
                 derived_source_path=str(reference_path), derived_source_sha256=sha(reference),
                 files={name:sha(data) for name,data in content.items()},
                 paper_edited=False, numerical_work=0, new_jobs=0, SU=0)
    assert source_path.read_bytes() == source and reference_path.read_bytes() == reference
    with (destination/'MANIFEST_v1.json').open('x') as stream:json.dump(proof,stream,indent=2)
    print(json.dumps(proof))


if __name__ == '__main__':main()
