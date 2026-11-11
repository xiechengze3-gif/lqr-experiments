"""Audit archived normalization and extract existing rank statistics; no learning."""
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'local_runs/ce-npg-initial-gap-20261028/report'
ORIGINAL = ROOT / 'local_runs/ce-npg-arguments-20261028/report'
OUT = ROOT / 'local_runs/ce-npg-rank-review-20261029'
DOC = ROOT / 'docs/CE_NPG_RELATIVE_RANK_REVIEW_20261029.md'
RANKS = (1, 2, 4, 8)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    with (REPORT / name).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(name, rows):
    with (OUT / name).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def key(row):
    return tuple(row[k] for k in ('algorithm', 'A_family', 'spectrum', 'n', 'r', 'mode'))


def exact(row):
    return (row['spectrum'] == 'exact' and row['n'] == '24'
            and int(row['r']) in RANKS and row['mode'] in ('dense', 'truncated'))


def median(row, metric):
    value = row[metric + '_median']
    return f'{float(value):.6g}' if value else '∞'


def budget(row, metric):
    value = row[metric + '_attainment_transitions']
    return f'{int(value):,}' if value else 'NR'


def main():
    # File identity and direct arithmetic checks, not new statistical estimates.
    manifest = {}
    for line in (REPORT / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        assert sha(REPORT / name) == expected, name
        manifest[name] = expected
    summary = json.loads((REPORT / 'summary.json').read_text(encoding='utf-8'))
    for name, expected in summary['input_files_sha256'].items():
        assert sha(ORIGINAL / name) == expected, name
    certificates = {
        item['task_id']: item for item in
        json.loads((ORIGINAL / 'system_certificates.json').read_text(encoding='utf-8'))
    }
    row_count = stable_count = failed_count = 0
    mismatch = 0.0
    sample = None
    with (ORIGINAL / 'all_records.csv').open(encoding='utf-8', newline='') as old_stream, \
            (REPORT / 'normalized_records.csv').open(encoding='utf-8', newline='') as new_stream:
        for old, new in itertools.zip_longest(csv.DictReader(old_stream), csv.DictReader(new_stream)):
            assert old is not None and new is not None
            for field in ('task_id', 'mode', 'transitions', 'stage', 'stable'):
                assert old[field] == new[field], (field, old['task_id'])
            certificate = certificates[new['task_id']]
            denominator = float(new['initial_gap'])
            assert denominator == certificate['initial_gap'] > 0
            assert math.isclose(denominator, certificate['J0'] - certificate['Jstar'],
                                rel_tol=1e-10, abs_tol=1e-10)
            row_count += 1
            if new['stable'] == 'True':
                stable_count += 1
                gap = float(new['absolute_gap'])
                relative = float(new['relative_initial_gap'])
                assert gap == float(old['gap'])
                assert relative == float(old['relative_gap'])
                assert new['failure_inclusive_relative_gap'] == new['relative_initial_gap']
                error = abs(relative - gap / denominator) / max(1.0, abs(relative))
                mismatch = max(mismatch, error)
                assert error < 1e-12
                if (sample is None and exact(new) and new['r'] == '4'
                        and new['algorithm'] == 'NPG' and new['A_family'] == 'scalar'
                        and new['mode'] == 'truncated' and new['stage'] == '48'):
                    sample = {k: new[k] for k in
                              ('task_id', 'initial_gap', 'absolute_gap', 'relative_initial_gap')}
            else:
                failed_count += 1
                assert new['relative_initial_gap'] == new['absolute_gap'] == ''
                assert new['failure_inclusive_relative_gap'] == 'inf'
                assert new['failure_inclusive_absolute_gap'] == 'inf'
    assert row_count == 96600 and failed_count == 8690 and mismatch == 0

    aggregate = read('aggregate_absolute_relative.csv')
    paths = [row for row in aggregate if exact(row)]
    terminal_by_key = {}
    for row in paths:
        group = key(row)
        if group not in terminal_by_key or int(row['transitions']) > int(terminal_by_key[group]['transitions']):
            terminal_by_key[group] = row
    terminal = sorted(terminal_by_key.values(), key=lambda r: (r['algorithm'], r['A_family'], int(r['r']), r['mode']))
    assert len(terminal) == 32 and all(row['count'] == '24' for row in terminal)
    thresholds = [row for row in read('attainment_side_by_side.csv') if exact(row)]
    assert len(thresholds) == 96
    thresholds.sort(key=lambda r: (r['algorithm'], r['A_family'], int(r['r']), float(r['epsilon']), r['mode']))
    fullrank_by_key = {}
    for row in aggregate:
        if row['n'] == '16' and row['spectrum'] in ('gapped', 'smooth', 'flat'):
            group = key(row)
            if group not in fullrank_by_key or int(row['transitions']) > int(fullrank_by_key[group]['transitions']):
                fullrank_by_key[group] = row
    fullrank = sorted(fullrank_by_key.values(), key=key)
    for algorithm, family, spectrum in itertools.product(('CE', 'NPG'), ('scalar', 'dense'), ('gapped', 'smooth')):
        modes = {row['mode'] for row in fullrank if
                 (row['algorithm'], row['A_family'], row['spectrum']) == (algorithm, family, spectrum)}
        assert modes == ({'k0', 'k1', 'k2', 'k3', 'k4', 'k6', 'k8', 'k12', 'dense'}
                         | ({'adaptive'} if algorithm == 'CE' else set()))

    OUT.mkdir(parents=True, exist_ok=True)
    write_csv('exact_rank_all_saved_budgets.csv', paths)
    write_csv('exact_rank_terminal.csv', terminal)
    write_csv('exact_rank_precision_budgets.csv', thresholds)
    write_csv('fullrank_terminal_all_saved_modes.csv', fullrank)
    lookup = {(r['algorithm'], r['A_family'], int(r['r']), r['mode']): r for r in terminal}
    threshold_lookup = {(r['algorithm'], r['A_family'], int(r['r']), r['mode']): r
                        for r in thresholds if float(r['epsilon']) == 0.1}
    lines = [
        '# CE/NPG 相对误差与多秩结果复核（2026-10-29）', '',
        '本次直接核对并提取已有结果，未重新运行学习、策略评价或绘图，未提交新的 Grace 作业。', '',
        '## 相对误差的准确含义', '',
        r'\[e_{\rm rel}(K)=\frac{J(K)-J_\star}{J(K_0)-J_\star}.\]', '',
        '每个系统、每个输出先除以自己的初始 optimality gap，再对全部24个重复取中位数。',
        'e=0.1表示还剩初始gap的10%；e>1表示比初始策略更差。CE分母同样是K0，而非首个拟合输出。',
        '独立逐行核对全部96,600个输出：归一化除法与原始保存值完全一致，最大差异0；',
        '全部8,690个失败输出仍按∞进入失败包含统计。没有用两个中位数之比代替逐实例归一化。', '',
        f"例如一个r=4截断NPG终端输出：{sample['absolute_gap']} / {sample['initial_gap']} = {sample['relative_initial_gap']}。", '',
        '## Exact-rank：固定 n=m=24，真实秩 r=1、2、4、8', '',
        '这是四种真实系统秩的比较；已知秩截断方法保留k=r。每格24个重复，分别给出scalar A与耦合dense A。',
        '以下都在各路线的固定终端预算比较dense与truncated：CE为12,432 transitions，NPG为25,075,008 transitions。',
        '表内每对数字均为dense / truncated，relative为初始gap的比例。∞为保留失败后的中位数，不是缺失值。', '',
    ]
    for family, label in [('scalar', 'A=0.5I'), ('dense', '耦合dense A')]:
        lines += [f'### {label}', '',
                  '|r|CE absolute|CE relative|NPG absolute|NPG relative|NPG稳定数/24|',
                  '|---:|---:|---:|---:|---:|---:|']
        for rank in RANKS:
            pairs = {}
            for alg in ('CE', 'NPG'):
                d, t = (lookup[(alg, family, rank, mode)] for mode in ('dense', 'truncated'))
                for metric in ('absolute', 'relative_initial'):
                    pairs[(alg, metric)] = median(d, metric) + ' / ' + median(t, metric)
                pairs[(alg, 'stable')] = d['stable_count'] + '/24 → ' + t['stable_count'] + '/24'
            lines.append(f"|{rank}|{pairs[('CE','absolute')]}|{pairs[('CE','relative_initial')]}|"
                         f"{pairs[('NPG','absolute')]}|{pairs[('NPG','relative_initial')]}|{pairs[('NPG','stable')]}|")
        lines += ['', 'CE在这四个秩的两个方法中均为24/24稳定。', '',
                  f'![CE逐秩absolute/relative](../local_runs/ce-npg-initial-gap-20261028/report/appendix_ce_rank_absolute_relative_{family}.png)', '',
                  f'![NPG逐秩absolute/relative](../local_runs/ce-npg-initial-gap-20261028/report/appendix_npg_rank_absolute_relative_{family}.png)', '']
    lines += ['## 固定相对精度10%的预算', '',
              '首个已测预算至少22/24成功才记达标。每格dense / truncated；NR为最大已测预算仍未达标。', '',
              '|A|r|CE absolute≤0.1|CE relative≤0.1|NPG absolute≤0.1|NPG relative≤0.1|',
              '|---|---:|---:|---:|---:|---:|']
    for family, label in [('scalar', '0.5I'), ('dense', '耦合A')]:
        for rank in RANKS:
            cells = []
            for alg in ('CE', 'NPG'):
                for metric in ('absolute', 'relative'):
                    cells.append(' / '.join(budget(threshold_lookup[(alg, family, rank, mode)], metric)
                                            for mode in ('dense', 'truncated')))
            lines.append(f'|{label}|{rank}|' + '|'.join(cells) + '|')
    lines += ['', '10%/3%/1%全部96行逐秩预算记录均保存在下方CSV；不把NR换成有限预算。', '',
              '## 逐秩结论与边界', '',
              '- CE在四个秩均获益，低秩时dense与truncated的差距更明显；r增大后优势缩小。',
              '- NPG在r=1、2、4的截断方法均24/24稳定，终端相对gap明显小于dense；r=8依旧失败严重：scalar A两者均0/24稳定，耦合A为dense 0/24、truncated 6/24。',
              '- n24的四个秩下，NPG两种方法均未达到至少22/24成功的相对10%标准；稳定性收益不能写成高精度达标。',
              '- 跨真实秩时初始gap也变化，relative下降不能单独证明高秩更容易。scalar A的截断NPG从r1到r4，absolute中位数0.0511→0.1395，relative却0.2549→0.1739，因此保留两种口径。',
              '- 已有网格是n24上的四个真实秩，以及r2上的n12/24/48维度扫描；没有把它描述成所有n×r的完整笛卡尔网格。', '',
              '## 满秩系统的截断秩 k 扫描', '',
              '这与上面的真实秩r变化是两个实验：满秩系统固定rank(B)=16，改变算法保留的k。',
              'gapped与smooth谱在CE/NPG及两种A上均包含k=0、1、2、3、4、6、8、12、16；k16以dense记载。CE另有adaptive。',
              'scalar A的NPG终端relative：gapped谱k2为0.10695、k8为0.15712、dense为0.17419；',
              'smooth谱k2为0.22230、k8为0.11103、dense为0.11983。最佳保留秩随谱而变。',
              '平坦谱NPG已有k2/k8/dense对照，relative分别0.38408/0.04137/0.01334，强截断损害性能。',
              '不将平坦谱NPG的三个已有方法描述成九秩完整扫描。', '',
              '## 可复核文件', '',
              '- [全部逐秩学习曲线数据](../local_runs/ce-npg-rank-review-20261029/exact_rank_all_saved_budgets.csv)',
              '- [32行逐秩终端统计](../local_runs/ce-npg-rank-review-20261029/exact_rank_terminal.csv)',
              '- [96行逐秩absolute/relative达标预算](../local_runs/ce-npg-rank-review-20261029/exact_rank_precision_budgets.csv)',
              '- [满秩各已有方法终端统计](../local_runs/ce-npg-rank-review-20261029/fullrank_terminal_all_saved_modes.csv)',
              '- [独立归一化与覆盖复核收据](../receipts/ce-npg-rank-review-20261029.json)',
              '- [原归一化补充完整结论](CE_NPG_INITIAL_GAP_FINDINGS_20261028.md)', '']
    DOC.write_text('\n'.join(lines), encoding='utf-8')
    receipt = {
        'status': 'PASS', 'operation': 'audit and extract existing rank statistics only',
        'normalization': '(J(K)-Jstar)/(J(K0)-Jstar), per instance before aggregation',
        'independently_audited_outputs': row_count, 'stable_outputs': stable_count,
        'failed_outputs_preserved': failed_count, 'maximum_normalization_scaled_mismatch': mismatch,
        'exact_true_ranks': list(RANKS), 'exact_n_equals_m': 24,
        'exact_terminal_rows': len(terminal), 'exact_all_budget_rows': len(paths),
        'exact_precision_rows': len(thresholds), 'fullrank_terminal_rows': len(fullrank),
        'new_learning_runs': 0, 'new_training_transitions': 0, 'new_control_solves': 0,
        'new_plotting_jobs': 0, 'new_Grace_jobs': 0,
        'verified_original_report_files': len(manifest),
        'inputs_sha256': {name: sha(REPORT / name) for name in
                          ('normalized_records.csv', 'aggregate_absolute_relative.csv', 'attainment_side_by_side.csv')},
        'outputs_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [DOC] + sorted(OUT.glob('*.csv'))},
        'example_r4_normalization': sample,
    }
    (ROOT / 'receipts/ce-npg-rank-review-20261029.json').write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({k: receipt[k] for k in ('status', 'independently_audited_outputs',
        'failed_outputs_preserved', 'maximum_normalization_scaled_mismatch', 'exact_terminal_rows',
        'exact_precision_rows', 'fullrank_terminal_rows', 'new_learning_runs', 'new_Grace_jobs')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
