"""Read completion metadata for Windows retrieval; performs no analysis."""
import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument('--report-root', required=True)
args = parser.parse_args()
root = Path(args.report_root)
summary = json.loads((root / 'summary.json').read_text())
audit = json.loads((root / 'numerical_audit.json').read_text())
supplement = json.loads((root / 'supplement' / 'provenance.json').read_text())
assert summary['status'] == 'complete'
assert audit['status'] == 'PASS' and audit['coverage'] == 'complete'
assert supplement['status'] == 'complete'
print(json.dumps(dict(status=summary['status'], complete_tasks=summary['complete_tasks'],
    sampled_method_groups=summary['sampled_method_groups'], stable_method_groups=summary['stable_method_groups'],
    audit_status=audit['status'], coverage=audit['coverage'], supplement_status=supplement['status'])))
