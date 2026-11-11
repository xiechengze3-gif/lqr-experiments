"""Apply Claude's accepted A1 to a new directory; preserve all v1 files."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent


def replace_once(text,old,new):
    assert old in text,repr(old)
    return text.replace(old,new)


def main():
    names=['frozen_engine.py','estimation.py','analyze_saved.py','plot_saved.py',
           'verify_saved.py','remote_ops.py','accounting.py','plan_after_resource.py',
           'build_resource_release.py','build_later_release.py']
    contents={name:(SOURCE/name).read_text(encoding='utf-8-sig') for name in names}
    # Preserve engine bytes exactly; transform only new copies of other files.
    for name in names:
        if name=='frozen_engine.py':continue
        data=contents[name]
        data=data.replace('config-X6a-v1.json','config-X6a-v2.json')
        data=data.replace('PROTOCOL_X6a_v1.md','PROTOCOL_X6a_A1.md')
        data=data.replace("'prepare_protocol.py',",'')
        data=data.replace("ROOT.parents[1]/'CLAUDE_TASK.md'",
            "next(p/'CLAUDE_TASK.md' for p in ROOT.parents if (p/'CLAUDE_TASK.md').exists())")
        contents[name]=data
    data=contents['estimation.py']
    data=replace_once(data,"prefixes=config['blocks']; rows=[]; artifacts=[]",
        "prefixes=config['blocks']; rows=[]; artifacts=[]\n    stein_grid=config['stein_blocks_by_n'][str(n)]")
    data=replace_once(data,"for item in collector(s,prefixes,random,cfg):",
        "for item in collector(s,stein_grid if algorithm=='Stein' else prefixes,random,cfg):")
    contents['estimation.py']=data
    data=contents['analyze_saved.py']
    data=replace_once(data,"assert len(receipt['artifacts'])==10",
        "stein_grid=config['stein_blocks_by_n'][str(spec['n'])]\n            assert len(receipt['artifacts'])==len(stein_grid)+len(config['blocks'])")
    data=replace_once(data,"for N in config['blocks']:","for N in stein_grid:")
    data=replace_once(data,"ce=np.load(folder/('CE-'+str(N)+'.npz'))",
        "ce=np.load(folder/('CE-'+str(N)+'.npz')) if N in config['blocks'] else None")
    data=replace_once(data,"('PI',dense_pi,trunc_pi,target_joint),\n                       ('CE',ce['Bhat'],e.trunc(ce['Bhat'],2),b)]",
        "('PI',dense_pi,trunc_pi,target_joint)]\n                if ce is not None:\n                    pairs.append(('CE',ce['Bhat'],e.trunc(ce['Bhat'],2),b))")
    data=replace_once(data,"assert len(rows)==11200 and checked==3200",
        "assert len(rows)==12800 and checked==3520")
    data=replace_once(data,"assert len(candidates)==5",
        "assert len(candidates)==len(config['stein_blocks_by_n'][str(n)])")
    data=replace_once(data,"max(config['blocks'])",
        "max(config['stein_blocks_by_n'][str(n)])")
    data=replace_once(data,"cells=320,prefixes_each=1600,",
        "cells=320,stein_prefixes=1920,ce_prefixes=1600,")
    contents['analyze_saved.py']=data
    data=contents['verify_saved.py']
    data=data.replace('len(rows)==11200','len(rows)==12800')
    data=replace_once(data,"row['censored_above_N']=='524288'",
        "row['censored_above_N']==str(max(config['stein_blocks_by_n'][row['n']]))")
    contents['verify_saved.py']=data
    data=contents['plot_saved.py']
    data=replace_once(data,"labels=['2k','8k','32k','131k','524k']",
        "labels=[('%.2gM'%(v/1e6)) if v>=1e6 else ('%gk'%(v/1024)) for v in x]")
    contents['plot_saved.py']=data
    data=contents['plan_after_resource.py']
    data=replace_once(data,"assert receipt['spec']==spec and len(receipt['rows'])==10",
        "assert receipt['spec']==spec and len(receipt['rows'])==(12 if spec['n']>=48 else 10)")
    data=replace_once(data,"assert minutes<=30,'Measured job plan exceeds provisional formal ceiling: revise before submitting.'",
        "assert minutes<=60,'A1 measured FORMAL request exceeds40 SU: report before submitting.'")
    contents['plan_after_resource.py']=data
    data=contents['build_later_release.py']
    data=replace_once(data,"assert 1<=minutes<=30 if a.stage=='FORMAL' else minutes==60",
        "assert 1<=minutes<=60 if a.stage=='FORMAL' else minutes==60")
    contents['build_later_release.py']=data
    config=json.loads((SOURCE/'config-X6a-v1.json').read_text())
    config.update(version=2,amendment='A1_Claude_20:20_ACCEPTED',
                  stein_blocks_by_n={str(n):config['blocks']+([2097152,4194304] if n>=48 else [])
                                     for n in config['n_values']},
                  provisional_X6a_requested_ceiling_SU=43,
                  formal_requested_SU_report_threshold=40)
    assert not (ROOT/'config-X6a-v2.json').exists()
    (ROOT/'config-X6a-v2.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8',newline='\n')
    for name,text in contents.items():
        path=ROOT/name;assert not path.exists()
        ast.parse(text,filename=name)
        if name=='frozen_engine.py':path.write_bytes((SOURCE/name).read_bytes())
        else:path.write_text(text,encoding='utf-8',newline='\n')
    proto=(SOURCE/'PROTOCOL_X6a_v1.md').read_text(encoding='utf-8-sig')
    prefix='''# X6a accepted amendment A1 — registry v2

This new copy preserves the original protocol and all v1 source files in its
parent. Claude's Review20:20 explicitly ACCEPTED the protocol with A1 and
authorized the resource PILOT (2 requested SU). A1 takes precedence over the
original text reproduced below:

- Stein at n48/72 additionally records N2097152 and4194304, both S and U.
  n24/36 remain at the original five N. CE remains at the original five N.
- Counts:320 paths,1920 Stein prefixes,1600 CE prefixes,3520 raw fit archives,
  12800 observation rows (NPG2 +PI2 +raw-PI1 per Stein prefix; CE2 per CE prefix).
- All resource tasks run to their applicable maximum. Resource request remains
  8x1CPU/2GiB/15min =2SU, no automatic retry. Report measured per-cell timing.
- Formal planning may reach40 requested SU; if it exceeds40, report before
  submission and await explicit acceptance. Provisional X6a ceiling is43 SU
  (resource2, formal<=40, report<=1), leaving357 of the separate400 for X6b/c.
- Config is config-X6a-v2.json, protocol is PROTOCOL_X6a_A1.md; SHA256SUMS in
  this amendment directory freezes their actual sources. Analysis remains draft
  until frozen with FORMAL. Only the grid/count/cost changes above are applied.
- Right-censoring thresholds use the applicable n-specific maximum; no extension
  is made for n24/36 or for CE. No scientific readout exists at amendment time.

Original v1 protocol follows for unchanged methods; its old file names, grid,
prefix totals and23-SU provisional estimate are superseded by this preface.

---

'''
    (ROOT/'PROTOCOL_X6a_A1.md').write_text(prefix+proto,encoding='utf-8',newline='\n')
    files=['frozen_engine.py','estimation.py','config-X6a-v2.json','PROTOCOL_X6a_A1.md']
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}
    (ROOT/'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name,digest in hashes.items()),
                                  encoding='utf-8',newline='\n')
    assert hashes['frozen_engine.py']=='9915fc38593be00eaa2e62718a0b527d9f95d2b190be39f6af8acd3827bea989'
    print(json.dumps(dict(status='A1_PREPARED_NO_NUMERICAL_RUN',hashes=hashes)))


if __name__=='__main__':main()
