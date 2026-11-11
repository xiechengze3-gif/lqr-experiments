"""Submit only the frozen X9 saved-data report, after complete formal proof."""
import fcntl
import json
import re
import subprocess
import time
from pathlib import Path
import remote_x9 as ops


def main():
    root = Path(__file__).resolve().parent
    ops.verify(root)
    assert root.parent == ops.BASE/'releases'
    approval = json.loads((root/'report-approval.json').read_text())
    review = root/'CLAUDE_TASK_REPORT_authorized.md'
    assert ops.sha(review) == approval['review_sha256']
    assert approval['exact_report_quote'] in review.read_text(encoding='utf-8-sig')
    assert 'Then REPORT as in X9 GO.' in approval['exact_report_quote']
    coverage_path = ops.OUT/'formal-v1/FORMAL_COVERAGE_v1.json'
    coverage = json.loads(coverage_path.read_text())
    assert ops.sha(coverage_path) == approval['formal_proof_sha256']
    assert coverage['status'] == 'FORMAL_COMPLETE_COVERAGE_SOURCES_COUNTS_RECEIPTS'
    assert coverage['bundles'] == 384 and coverage['paired_paths'] == 1024
    assert coverage['config_sha256'] == ops.sha(root/'formal-config.json')
    with (ops.OUT/'submission.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        name = 'x9-20261106-report-v1'
        receipt = ops.OUT/'submissions'/(name+'.json')
        assert not receipt.exists(), 'Inspect existing receipt; never replay.'
        ledger_path = ops.OUT/'budget/ledger.json'
        ledger = json.loads(ledger_path.read_text())
        assert ledger['cap_requested_SU'] == 50
        assert abs(ledger['cumulative_requested_SU']-47.93333333333334) < 1e-9
        assert ledger['cumulative_requested_SU']+2 <= 50
        assert not any(r['stage'] == 'REPORT' for r in ledger['submissions'])
        assert not (ops.OUT/'report-v1').exists()
        balance = subprocess.check_output(['myproject'], universal_newlines=True)
        account = next(line for line in balance.splitlines() if '|'+ops.ACCOUNT+'|' in line)
        assert float(account.split('|')[6].strip()) >= 2
        command = ['sbatch', '--parsable', '-A', ops.ACCOUNT, '-p', 'short',
                   '--ntasks=1', '--cpus-per-task=1', '--mem=2048M', '-t', '120',
                   '--array=0-0%1', '-J', name,
                   '-o', str(ops.OUT/'logs'/(name+'-%A_%a.out')), str(root/'report.sbatch')]
        row = dict(id=name, stage='REPORT', experiment='X9', job=None,
                   status='RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY', requested_bound_SU=2.,
                   command=command, epoch=time.time(), approval=approval,
                   release=str(root), release_manifest_sha256=ops.sha(root/'SHA256SUMS'),
                   balance_snapshot=balance, automatic_retries=0)
        ops.save(receipt, row)
        ledger['submissions'].append(row)
        ledger['cumulative_requested_SU'] += 2
        ops.save(ledger_path, ledger)
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        row.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        if result.returncode == 0 and re.fullmatch(r'\d+(;[^\s]+)?', result.stdout.strip()):
            row.update(job=result.stdout.strip().split(';')[0], status='SUBMITTED')
        else:
            row['status'] = 'RECONCILE_REQUIRED_NO_AUTOMATIC_RETRY'
        ops.save(receipt, row)
        ledger['submissions'][-1] = row
        ops.save(ledger_path, ledger)
        print(json.dumps(row), flush=True)
        assert row['status'] == 'SUBMITTED'


if __name__ == '__main__':
    main()
