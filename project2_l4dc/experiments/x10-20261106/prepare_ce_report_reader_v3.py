"""Correct Windows path grouping only; preserve failed reader and frozen statistics."""
import ast
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    source=HERE/'ce-src-v2/analyze_ce.py';text=source.read_text(encoding='utf-8')
    original_line="        target = x8_rows if ref['path'].startswith('x8/') else dimension if ref['path'].startswith('dimension/') else redundancy"
    corrected_line="        target = x8_rows if Path(ref['path']).parts[0] == 'x8' else dimension if Path(ref['path']).parts[0] == 'dimension' else redundancy"
    assert text.count(original_line)==1 and text.count("out = ROOT/'ce-report-v2'")==1
    changed=text.replace(original_line,corrected_line).replace("out = ROOT/'ce-report-v2'","out = ROOT/'ce-report-v3'")
    assert changed.replace(corrected_line,original_line).replace("out = ROOT/'ce-report-v3'","out = ROOT/'ce-report-v2'")==text
    before={n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
    after={n.name:ast.get_source_segment(changed,n) for n in ast.parse(changed).body if isinstance(n,ast.FunctionDef)}
    for name in ['write_csv','q','cost','merge_bytes']:assert before[name]==after[name],name
    whole=json.loads((HERE/'ce-formal-v2/FORMAL_DONE.json').read_text(encoding='utf-8'))
    counts=dict(x8=0,dimension=0,redundancy=0)
    for ref in whole['paths']:
        part=Path(ref['path']).parts[0]
        assert part in counts
        d=json.loads((HERE/'ce-formal-v2'/ref['path']/'DONE.json').read_text(encoding='utf-8'))
        counts[part]+=len(d['records'])
    assert counts==dict(x8=122880,dimension=2432,redundancy=768)
    assert (HERE/'ce-report-v2').exists() and not any((HERE/'ce-report-v2').iterdir())
    target=HERE/'ce-report-src-v3';assert not target.exists();target.mkdir()
    with (target/'analyze_ce.py').open('x',encoding='utf-8',newline='\n') as stream:stream.write(changed)
    for old,new in [('render_ce_report.py','render_ce_report_v3.py'),('finalize_ce_report.py','finalize_ce_report_v3.py')]:
        data=(HERE/old).read_text(encoding='utf-8')
        assert "ce-report-v2" in data
        data=data.replace('ce-report-v2','ce-report-v3')
        with (HERE/new).open('x',encoding='utf-8',newline='\n') as stream:stream.write(data)
    launcher=(HERE/'Launch-CE-v3.ps1').read_text(encoding='utf-8')
    launcher=launcher.replace("ValidateSet('pilot','formal','report')","ValidateSet('report')")
    launcher=launcher.replace("report='ce-report-v2'","report='ce-report-v3'")
    launcher=launcher.replace("'ce-src-v2\\analyze_ce.py'","'ce-report-src-v3\\analyze_ce.py'")
    marker="$env:PATH = 'E:\\anaconda;E:\\anaconda\\Library\\bin;E:\\anaconda\\Scripts;' + $env:PATH"
    assert launcher.count(marker)==1
    launcher=launcher.replace(marker,marker+"\n$env:PYTHONPATH = Join-Path $PSScriptRoot 'ce-src-v2'")
    with (HERE/'Launch-CE-Report-v3.ps1').open('x',encoding='utf-8',newline='\n') as stream:stream.write(launcher)
    renderer=(HERE/'Render-CE.ps1').read_text(encoding='utf-8').replace("'render_ce_report.py'","'render_ce_report_v3.py'")
    with (HERE/'Render-CE-v3.ps1').open('x',encoding='utf-8',newline='\n') as stream:stream.write(renderer)
    proof=dict(status='PASS_METADATA_READER_FIX_ONLY',old_analysis_sha256=sha(source.read_bytes()),
        new_analysis_sha256=sha((target/'analyze_ce.py').read_bytes()),changed_lines=[original_line.strip(),corrected_line.strip()],
        other_change='New output namespace ce-report-v3; empty failed ce-report-v2 preserved.',
        statistical_functions_literal_identical=['write_csv','q','cost','merge_bytes'],
        entire_main_reversible_except_reader_and_output_namespace=True,verified_record_counts=counts,
        frozen_config_sha256=sha((HERE/'ce-config-protocol-v2.json').read_bytes()),
        new_training_transitions=0,new_jobs=0,Grace_SU=0,old_results_modified=False,
        failed_attempt_statistics_started=False,files={name:sha((HERE/name).read_bytes()) for name in
        ['ce-report-src-v3/analyze_ce.py','render_ce_report_v3.py','finalize_ce_report_v3.py','Launch-CE-Report-v3.ps1','Render-CE-v3.ps1']})
    with (HERE/'CE_REPORT_READER_CORRECTION_v3.json').open('x') as stream:json.dump(proof,stream,indent=2)
    print(json.dumps({k:v for k,v in proof.items() if k!='files'}))


if __name__=='__main__':main()
