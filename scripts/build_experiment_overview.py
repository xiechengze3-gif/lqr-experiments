"""Refresh the inventory in the consolidated LQR explanation without simulations.

Uses only the standard library. Reads existing results and writes the one report
under the project docs directory. Historical configs and result files are read-only.
"""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from itertools import groupby
from pathlib import Path
import csv
import json
import re


PROJECT = Path(__file__).resolve().parents[1]
RESULTS = Path('E:/ChatGPT/Results/LQR_experiments')
REPORT = PROJECT / 'docs/LQR_ALL_EXPERIMENTS_20261014.md'
BEGIN = '<!-- BEGIN GENERATED INVENTORY -->'
END = '<!-- END GENERATED INVENTORY -->'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def link(path, label=None):
    return f'[{label or path.name}]({path.resolve().as_posix().replace(" ", "%20")})'


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def table(headers, rows):
    return '\n'.join([
        '| ' + ' | '.join(headers) + ' |',
        '| ' + ' | '.join('---' for _ in headers) + ' |',
        *['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows],
    ]) + '\n\n'


def compact(value):
    """Encode consecutive repetition exactly, keeping large schedules readable."""
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items()}
    if isinstance(value, list):
        if len(value) > 12 and all(isinstance(v, (int, float, str)) for v in value):
            runs = [(v, len(list(g))) for v, g in groupby(value)]
            if len(runs) * 2 < len(value):
                return {'ordered_runs_value_count': runs, 'length': len(value)}
        return [compact(v) for v in value]
    return value


def task_lists(config):
    return {k: v for k, v in config.items()
            if isinstance(v, list) and v and all(isinstance(t, dict) for t in v)
            and (k == 'tasks' or k.endswith('_tasks'))}


def grid(tasks):
    fields = {}
    for task in tasks:
        for key, value in task.items():
            if key in ('id', 'old_raw', 'old_sha256'):
                continue
            if key == 'original_task' and isinstance(value, dict):
                for subkey, subvalue in value.items():
                    fields.setdefault('original_task.' + subkey, set()).add(
                        json.dumps(compact(subvalue), ensure_ascii=False, sort_keys=True))
            else:
                fields.setdefault(key, set()).add(
                    json.dumps(compact(value), ensure_ascii=False, sort_keys=True))
    return {k: [json.loads(v) for v in sorted(values)] for k, values in sorted(fields.items())}


def main():
    source = REPORT.read_text(encoding='utf-8')
    assert source.count(BEGIN) == source.count(END) == 1
    sections = ['## 最新 100 维的自动数值汇总\n\n']
    endpoint = RESULTS / 'historical-npg100-adaptive-20261012/report/endpoints.csv'
    with endpoint.open(encoding='utf-8-sig', newline='') as stream:
        records = list(csv.DictReader(stream))
    assert len(records) == 54
    methods = ['raw', 'truncated', 'adaptive_1']
    groups = {}
    for row in records:
        groups.setdefault((row['benchmark'], int(row['rank']), float(row['tail'])), []).append(row)
    rows = []
    for key, group in sorted(groups.items()):
        bench, rank, tail = key
        values = []
        for method in methods:
            subset = [r for r in group if r['method'] == method]
            assert len(subset) == 2
            stable = [r for r in subset if not r['failure'] and r['gap']]
            if len(stable) == 2:
                values.append(f'{sum(float(r["gap"]) for r in stable)/2:.6f}')
            else:
                values.append('；'.join(
                    f'seed{r["seed"]}：失稳' if r['failure'] else f'seed{r["seed"]}：{float(r["gap"]):.6f}'
                    for r in subset))
        rows.append([bench, rank, tail, *values])
    sections += ['每行两个系统的最终gap均值。存在失败的行列出逐系统结果，不以幸存者均值代替。\n\n',
                 table(['benchmark', 'r', '单个尾奇异值', 'Dense', '固定秩', 'Adaptive c1'], rows)]
    criteria = [
        ('rank80 r1/2/4/8', lambda r: r['benchmark'] == 'rank80' and int(r['rank']) <= 8),
        ('rank80 含r16', lambda r: r['benchmark'] == 'rank80'),
        ('tail256 全部尾部', lambda r: r['benchmark'] == 'tail256'),
    ]
    rows = []
    for name, condition in criteria:
        for eps in (1, 2, 5):
            values = []
            for method in methods:
                subset = [r for r in records if condition(r) and r['method'] == method]
                passed = sum(not r['failure'] and bool(r['gap']) and float(r['gap']) <= eps for r in subset)
                values.append(f'{passed}/{len(subset)}')
            rows.append([name, eps, *values])
    sections += ['下面仅统计固定最后输出达标数。它没有要求后续4点确认，也不是最小达标预算统计；不同benchmark分别统计。\n\n',
                 table(['范围', 'ε', 'Dense', '固定秩', 'Adaptive c1'], rows)]
    cases = {}
    for row in records:
        cases.setdefault(int(row['case_id']), {})[row['method']] = row
    rows = []
    for case, case_rows in sorted(cases.items()):
        first = case_rows['raw']
        gaps = ['失稳：' + case_rows[m]['failure'] if case_rows[m]['failure']
                else f'{float(case_rows[m]["gap"]):.6f}' for m in methods]
        rows.append([case, first['benchmark'], first['rank'], first['tail'], first['seed'],
                     first['planned_stages'], first['assigned_budget'], *gaps,
                     case_rows['adaptive_1']['retained_rank'] or '失败后缺失'])
    sections += ['### 100 维逐系统末端结果\n\n', table(
        ['case', 'benchmark', 'r', 'tail', 'seed', '轮数', '计划transitions',
         'Dense gap', '固定秩gap', 'Adaptive gap', 'Adaptive末端保留秩'], rows)]
    sections.append('## 全部当前配置索引\n\n')
    configs = sorted((PROJECT / 'configs').glob('*.json'))
    sections.append(f'共{len(configs)}个当前配置文件。任务数是manifest条目数；无tasks的索引、诊断和资源配置另列。'
                    '文件SHA256在参数摘要中完整记录，当前文件不代替历史冻结版本。\n\n')
    config_rows = []
    for path in configs:
        config = read_json(path)
        lists = task_lists(config)
        count = '；'.join(f'{k}={len(v)}' for k, v in lists.items()) or '无任务列表'
        tasks = [t for values in lists.values() for t in values]
        physical = [t.get('original_task', t) for t in tasks]
        dims = sorted({str(t['n']) for t in physical if 'n' in t})
        ranks = sorted({str(t['r']) for t in physical if 'r' in t})
        eps = {k: config[k] for k in ('targets', 'tolerances', 'absolute_epsilons', 'primary_tolerances') if k in config}
        config_rows.append([link(path), count, ','.join(dims) or '见参数', ','.join(ranks) or '见参数',
                            json.dumps(eps, ensure_ascii=False) if eps else '见参数／无单一ε'])
    sections.append(table(['配置', '条目数', 'n', 'r', '最终精度字段'], config_rows))
    sections.append('## 各配置的完整公共参数和任务取值范围\n\n')
    sections.append('以下逐文件列出全部公共参数及任务字段取值；精确的逐任务字段组合、ID和种子对应关系以该文件链接为准。'
                    'ordered_runs_value_count按顺序记录[数值,连续重复次数]，可无损还原采样排程。'
                    '任务取值范围是已列任务的并集，不表示所有字段笛卡尔积都被实际运行。\n\n')
    for path in configs:
        config = read_json(path)
        lists = task_lists(config)
        public = {k: compact(v) for k, v in config.items() if k not in lists}
        digest = sha256(path.read_bytes()).hexdigest()
        sections.append(f'### {path.stem.replace("_", " ").replace("-", " ")}\n\n')
        sections.append(f'原配置：{link(path)}。SHA256：`{digest}`。\n\n')
        sections.append('```json\n' + json.dumps(public, ensure_ascii=False, indent=2) + '\n```\n\n')
        for name, tasks in lists.items():
            sections.append(f'{name}共{len(tasks)}条，字段取值范围：\n\n```json\n' +
                            json.dumps(grid(tasks), ensure_ascii=False, indent=2) + '\n```\n\n')
    sections.append('## 冻结配置和额外执行配置\n\n')
    frozen = sorted((PROJECT / 'local_runs').rglob('configs/*.json'))
    extra = sorted((RESULTS / 'npg300-local-20261009').glob('*.json'))
    extra = [p for p in extra if p.name in ('config.json', 'active_scope.json', 'controlled_scope_switch.json')]
    rows = []
    for path in frozen + extra:
        rows.append([link(path, path.relative_to(PROJECT).as_posix() if path.is_relative_to(PROJECT)
                          else path.relative_to(RESULTS).as_posix()), sha256(path.read_bytes()).hexdigest()])
    sections.append(table(['冻结或额外配置', 'SHA256'], rows))
    sections.append('## 全部结果目录与保存状态\n\n')
    sections.append('以下包含正式结果、preview、review、diagnostics和迁移目录。raw文件数为物理JSON文件数，'
                    '可能包含重放、复用、验证及嵌套归档，不等于独立生产运行数。'
                    '“无顶层状态”表示应查阅对应报告／凭据；保存状态及时间不证明进程此刻活跃。'
                    '文件修改时间换算为America/Chicago，本轮2026年10月日期为UTC-05:00。\n\n')
    dirs = sorted(p for p in RESULTS.iterdir() if p.is_dir())
    for path in dirs:
        sections.append(f'### {path.name.replace("-", " ")}\n\n')
        sections.append(f'目录：{link(path, path.name)}。\n\n')
        statuses = []
        for name in ('pipeline_status.json', 'completion.json', 'study_progress.json', 'local-status.json'):
            item = path / name
            if item.exists():
                data = read_json(item)
                stamp = datetime.fromtimestamp(item.stat().st_mtime, timezone(timedelta(hours=-5))).isoformat(timespec='seconds')
                statuses.append(f'{link(item)}：{data.get("status", data.get("state", "见文件"))}，保存于{stamp}')
        sections.append('；'.join(statuses) + '。\n\n' if statuses else '无顶层状态文件；完成情况见对应研究说明与报告。\n\n')
        raw_files = list(path.rglob('raw/*.json'))
        sections.append(f'raw JSON文件数：{len(raw_files)}。\n\n')
        summaries = sorted(set(path.rglob('summary.json')) | set(path.rglob('research_summary.json')) |
                           set(path.rglob('integrated_summary.json')) | set(path.rglob('findings.md')))
        summaries = [p for p in summaries if 'REPORT_SCHEMA_FIXTURE_NOT_EXPERIMENT' not in p.parts]
        if summaries:
            sections.append('报告入口：\n\n' + '\n'.join(
                '- ' + link(p, p.relative_to(path).as_posix()) for p in summaries) + '\n\n')
    sections.append('## 协议和专题报告完整索引\n\n')
    docs = sorted(p for p in (PROJECT / 'docs').glob('*.md') if p != REPORT)
    sections.append('\n'.join('- ' + link(p) for p in docs) + '\n\n')
    sections.append('## 执行凭据和版本来源完整索引\n\n')
    receipts = sorted((PROJECT / 'receipts').glob('*.json'))
    sections.append('这些凭据用于核对release、hash、配置、执行、迁移、替代和下载来源；不根据凭据文件数累计科学重复。\n\n')
    sections.append('\n'.join('- ' + link(p) for p in receipts) + '\n\n')
    generated = ''.join(sections)
    updated = source.split(BEGIN)[0] + BEGIN + '\n\n' + generated + END + source.split(END)[1]
    # Check coverage and file links before saving the report.
    assert all(link(p) in updated for p in configs)
    assert all(link(p, p.name) in updated for p in dirs)
    for target in re.findall(r'\]\(([^)]+)\)', updated):
        if target.startswith(('E:/', 'C:/')):
            assert Path(target.replace('%20', ' ')).exists(), target
    assert sum(bool(r['failure']) for r in records if r['method'] == 'adaptive_1') == 1
    REPORT.write_text(updated, encoding='utf-8')
    print(json.dumps({'report': str(REPORT), 'bytes': REPORT.stat().st_size,
                      'current_configs': len(configs), 'frozen_configs': len(frozen),
                      'extra_configs': len(extra), 'result_directories': len(dirs),
                      'protocols_and_reports': len(docs), 'receipts': len(receipts),
                      'historical100_endpoints': len(records), 'all_local_links_exist': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
