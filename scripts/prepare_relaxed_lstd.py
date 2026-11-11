"""Freeze a tolerance-only revision while retaining the previous release."""
import json
import shutil
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    original = root / 'local_runs' / 'fixed-value-cumulative' / 'frozen'
    destination = root / 'local_runs' / 'fixed-value-relaxed-lstd' / 'frozen'
    assert destination.resolve().is_relative_to(root.resolve())
    if destination.exists():
        raise FileExistsError(destination)
    cfg = json.loads((original / 'configs' / 'fixed_value_suite.json').read_text())
    assert cfg['solver_rtol'] == 1e-8
    cfg['solver_rtol'] = 1e-6
    shutil.copytree(original, destination)
    manifest = destination / 'configs' / 'fixed_value_suite.json'
    manifest.write_text(json.dumps(cfg, indent=2) + '\n', encoding='utf-8')
    (root / 'configs' / 'fixed_value_relaxed_lstd.json').write_text(
        json.dumps(cfg, indent=2) + '\n', encoding='utf-8')
    for name in ('relaxed_lstd_bootstrap.py', 'relaxed_lstd_failed_batch.py'):
        shutil.copy2(root / 'scripts' / name, destination / 'scripts' / name)
    print(json.dumps(dict(frozen=str(destination), manifest=str(manifest), solver_rtol=cfg['solver_rtol'])))


if __name__ == '__main__':
    main()
