"""Render frozen X9 saved-data CSVs; no estimator, controller or trajectory changes."""
import argparse
import csv
import json
import math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import frozen_engine as e
import x9_core as core

COLORS = dict(dense='#df773c', truncated='#287bb5')


def read(path):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def fmt(value):
    if value is None or value == '':
        return 'N/A'
    x = float(value)
    if math.isnan(x):
        return 'N/A'
    return '∞' if math.isinf(x) else f'{x:.5g}'


def interval(row, arm, metric):
    prefix = arm+'_'+metric
    return f"{fmt(row[prefix+'_median'])} [{fmt(row[prefix+'_q25'])}, {fmt(row[prefix+'_q75'])}]"


def figure_cell(ax, rows, metric):
    rows = sorted(rows, key=lambda r: float(r['alpha']))
    x = np.array([float(r['alpha']) for r in rows])
    positive = [float(r[f'{arm}_{metric}_{suffix}']) for r in rows
                for arm in COLORS for suffix in ['median', 'q25', 'q75']
                if math.isfinite(float(r[f'{arm}_{metric}_{suffix}']))
                and float(r[f'{arm}_{metric}_{suffix}']) > 0]
    bottom = min(positive)/2 if positive else .001
    top = max(positive)*2.2 if positive else 1.
    for arm, color in COLORS.items():
        y, lo, hi = [np.array([float(r[f'{arm}_{metric}_{suffix}']) for r in rows])
                     for suffix in ['median', 'q25', 'q75']]
        finite = np.isfinite(y) & (y > 0)
        plotted = np.where(finite, y, np.nan)
        ax.plot(x, plotted, 'o-', color=color, label=arm, ms=4)
        valid_band = np.isfinite(lo) & np.isfinite(hi) & (lo > 0)
        ax.fill_between(x, lo, hi, where=valid_band, color=color, alpha=.13)
        for i, value in enumerate(y):
            if not math.isfinite(value):
                ax.plot(x[i], top/1.15, '^', color=color, ms=6)
                ax.annotate('∞', (x[i], top/1.15), xytext=(3, -8), textcoords='offset points', color=color, fontsize=8)
            elif value <= 0:
                ax.plot(x[i], bottom*1.15, 'v', color=color, ms=6)
                ax.annotate(fmt(value), (x[i], bottom*1.15), xytext=(3, 3), textcoords='offset points', color=color, fontsize=8)
            if math.isfinite(value) and value > 0 and math.isinf(hi[i]):
                ax.annotate('', (x[i], top/1.15), (x[i], value), arrowprops=dict(arrowstyle='->', color=color, lw=.7))
    ax.set_yscale('log')
    ax.set_ylim(bottom, top)
    ax.set_xticks(x, [f'{v:g}' for v in x])
    ax.set_xlabel('alpha')
    ax.grid(alpha=.2)
    failed = '; '.join(f"{float(r['alpha']):g}: {32-int(float(r['dense_stable']))}/{32-int(float(r['truncated_stable']))}" for r in rows)
    ax.text(.02, .03, 'Failures dense/truncated, each /32\n'+failed,
            transform=ax.transAxes, fontsize=6.8, va='bottom',
            bbox=dict(facecolor='white', alpha=.8, edgecolor='none'))
    ax.set_title(rows[0]['algorithm']+f"; rung={float(rows[0]['rung']):g}; M={int(float(rows[0]['primitive_per_arm'])):,}", fontsize=9)


def emit(fig, directory, name):
    files = []
    for ext in ['png', 'svg']:
        path = directory/(name+'.'+ext)
        assert not path.exists()
        fig.savefig(path, dpi=170, bbox_inches='tight')
        files.append(path)
    plt.close(fig)
    return files


def main(config_path):
    e.require_compute()
    config = json.loads(config_path.read_text())
    core.verify(config)
    root = core.OUT/'report-v1'
    proof = json.loads((root/'verification.json').read_text())
    assert proof['status'] == 'COMPLETE' and proof['config_sha256'] == e.sha(config_path)
    for name, digest in proof['files'].items():
        assert e.sha(root/name) == digest
    summary = read(root/'summary.csv')
    assert len(summary) == 80
    primary = [r for r in summary if r['ratio_kind'] == 'failure_inclusive']
    assert len(primary) == 40
    figures = root/'figures'
    assert not figures.exists()
    figures.mkdir()
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False,
                         'axes.spines.right': False, 'svg.fonttype': 'none'})
    generated = []
    for metric, label in [('gap', 'Absolute gap'), ('relative_gap', 'Gap / initial gap')]:
        fig, axes = plt.subplots(4, 2, figsize=(12, 12))
        for i, rung in enumerate(config['rungs']):
            for j, algorithm in enumerate(['NPG', 'PI']):
                rows = [r for r in primary if float(r['rung']) == rung and r['algorithm'] == algorithm]
                assert len(rows) == 5
                figure_cell(axes[i, j], rows, metric)
                axes[i, j].set_ylabel(label)
                if i == 0:
                    axes[i, j].legend(loc='upper right', fontsize=7)
        fig.suptitle('X9: full-population median/IQR, n=m=24, retained order 2\n'
                     'alpha=0 reuses X6b; alpha=.4 is the large-tail control. Empirical scan outside certified theorem conditions.', fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, .95))
        generated += emit(fig, figures, 'all_rungs_'+metric)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, algorithm in zip(axes, ['NPG', 'PI']):
        rows = [r for r in primary if float(r['rung']) == 1 and r['algorithm'] == algorithm]
        figure_cell(ax, rows, 'gap')
        ax.set_ylabel('Absolute gap')
        ax.legend(loc='upper right', fontsize=7)
    fig.suptitle('Full-rung comparison; alpha=0 reused; all failures retained. Median and IQR over 8 systems × 4 seeds.', fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, .92))
    generated += emit(fig, figures, 'full_rung_gap')
    derived = read(root/'transitions_saved_derived.csv')
    assert len(derived) == 10
    lines = ['# X9 saved-data report', '',
             'X9 is an empirical scan outside the certified conditions of Theorem 3 '
             '(fixed k=2, inherited empirical schedule and a large-tail control). '
             'These observations are not a verification of the theorem or an epsilon attainment guarantee.', '',
             'Family S; n=m=24; Q=R=W=I; K0=0; eta=.2, nu=1, H=16; '
             '16 pulse burn blocks and one baseline block per stage; NPG16/PI8 updates. '
             'All integer schedules and paired noise namespaces are frozen from X6b. '
             'Alpha=0 is the entire saved X6b n24 cell, not a new replication. '
             'Positive alphas use new trajectories and their own Kstar/Pstar/Jstar/initial gap. '
             'True-nullspace redundant-cost fields are N/A when alpha>0.', '',
             'All32 outputs enter each gap median/IQR; failures are +infinity. '
             'Paired ratios use matched system/seed paths; undefined both-failed ratios and bootstrap mass '
             'remain explicitly counted in summary.csv. Failure-inclusive and both-stable versions are both exported.', '',
             '|alpha|tau2_sq|algorithm|rung|M per arm|dense absolute [IQR]|truncated absolute [IQR]|dense stable|truncated stable|paired ratio [95% CI]|ratio pairs|',
             '|---:|---:|---|---:|---:|---|---|---:|---:|---|---:|']
    for r in sorted(primary, key=lambda r: (float(r['alpha']), r['algorithm'], float(r['rung']))):
        lines.append('|'+ '|'.join([fmt(r['alpha']), fmt(r['tau2_sq']), r['algorithm'], fmt(r['rung']),
            str(int(float(r['primitive_per_arm']))), interval(r, 'dense', 'gap'), interval(r, 'truncated', 'gap'),
            r['dense_stable']+'/32', r['truncated_stable']+'/32',
            f"{fmt(r['paired_ratio_median'])} [{fmt(r['ci_low'])}, {fmt(r['ci_high'])}]", r['ratio_pairs']])+'|')
    lines += ['', '|alpha|algorithm|rung|dense relative [IQR]|truncated relative [IQR]|',
              '|---:|---|---:|---|---|']
    for r in sorted(primary, key=lambda r: (float(r['alpha']), r['algorithm'], float(r['rung']))):
        lines.append('|'+ '|'.join([fmt(r['alpha']), r['algorithm'], fmt(r['rung']),
            interval(r, 'dense', 'relative_gap'), interval(r, 'truncated', 'relative_gap')])+'|')
    lines += ['', 'Relative-gap medians/IQR, all first-failure stages, padding and all ratio definitions '
              'are in summary.csv; endpoints.csv and failures.csv retain individual records. '
              'Figures use the same full32 gap columns, not stability-conditioned gaps.', '',
              '|alpha|algorithm|dense target gap at full rung|truncated M to match|saving factor|left censored|right censored|unbracketed|target identified|',
              '|---:|---|---:|---:|---:|---|---|---|---|']
    for r in derived:
        lines.append('|'+ '|'.join([fmt(r['alpha']), r['algorithm'], fmt(r['dense_gap_at_N_cal']),
            fmt(r['truncated_N_to_match']), fmt(r['factor']), r['left_censored'],
            r['right_censored'], r['unbracketed'], r['target_identified']])+'|')
    lines += ['', 'Matching transitions are descriptive first log-log crossings of the failure-inclusive median '
              'curves on the four-rung grid, using the frozen paper cross arithmetic. No smoothing or extrapolation. '
              'Left-censored values are bounds, right-censored/unbracketed/nonfinite targets remain flagged. '
              'The separate summary.csv columns preserve both absolute and relative normalization.', '',
              'Spend and final accounting are delivered from the X9 ledger/Slurm/AMS snapshots separately; '
              'requested upper bounds are not already-consumed SU, and Slurm and AMS are not added.', '',
              'No old results, releases or paper tex were edited.']
    report_path = root/'SCIENCE_REPORT.md'
    with report_path.open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines)+'\n')
    generated.append(report_path)
    core.save_new(root/'RENDER_COMPLETE_v1.json', dict(status='SAVED_CSV_FIGURES_TABLES_RENDERED',
        source_sha256=e.sha(__file__), frozen_analysis_sha256=proof['source_sha256'],
        config_sha256=e.sha(config_path), job=__import__('os').environ['SLURM_JOB_ID'],
        files={str(p.relative_to(root)): e.sha(p) for p in generated},
        no_new_training_transitions=True, plot_gap_denominator='FULL32_FAILURE_INCLUSIVE'))
    print(json.dumps(dict(status='RENDERED', files=len(generated))), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True, type=Path)
    main(p.parse_args().config)
