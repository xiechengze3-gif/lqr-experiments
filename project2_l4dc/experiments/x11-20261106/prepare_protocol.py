"""Prepare a new immutable local-only rectangular CE study; zero simulation."""
import ast, hashlib, json
from pathlib import Path
R=Path(__file__).resolve().parent; C=R.parents[1]
X=R.parent/'x10-20261106'; S=X/'ce-src-v2'; D=R/'src-v1'
review=hashlib.sha256((C/'CLAUDE_TASK.md').read_bytes()).hexdigest()
assert 'X11 construction ACCEPTED; X10b scheduling OK (13:30 CDT 11/06)' in (C/'CLAUDE_TASK.md').read_text(encoding='utf-8')
assert (R/'CONSTRUCTION_NOTICE_v1.md').exists()
D.mkdir()
def put(p,s):
    with p.open('xb') as f:f.write(s if isinstance(s,bytes) else s.encode())
for name in ['frozen_engine.py','s_ce_original.py','ce_reference_local.py']:
    put(D/name,(S/name).read_bytes())
original=(S/'s_ce_original.py').read_text()
rect=original
edits={
 'def model(family, n, system):':'def model(family, n, system, m=None):\n    m=n if m is None else m\n    assert family=="S" and min(n,m)>=2',
 'v = e.haar(e.rng(3, n, n, system), n)':'v = e.haar(e.rng(3, n, m, system), m)',
 'eye = np.eye(n)':'eye = np.eye(n)\n    eye_m = np.eye(m)',
 'k0 = np.zeros((n, n))':'k0 = np.zeros((m, n))',
 'ps = solve_discrete_are(a, b, eye, eye)':'ps = solve_discrete_are(a, b, eye, eye_m)',
 'ks = np.linalg.solve(eye +':'ks = np.linalg.solve(eye_m +',
 "cert = dict(family='S', n=n, m=n,":"cert = dict(family='S', n=n, m=m,",
 'return dict(A=a, B=b, Q=eye, R=eye,':'return dict(A=a, B=b, Q=eye, R=eye_m,'}
for a,b in edits.items():assert rect.count(a)==1;rect=rect.replace(a,b)
put(D/'rectangular.py',rect)
source=(S/'ce_driver.py').read_text(); names=['sha','save_new','peak_memory_bytes','save_model','run_shared_ce','equivalence']
functions={node.name:ast.get_source_segment(source,node) for node in ast.parse(source).body if isinstance(node,ast.FunctionDef)}
imports='import ctypes,json,math,os,platform,time\nfrom pathlib import Path\nimport hashlib,numpy as np\nimport frozen_engine as e\nimport s_ce_original as original\nimport ce_reference_local as reference\n'
core=imports+'\n\n'.join(functions[n] for n in names)+'\n'
assert core.count('LOCAL_AUTHOR_APPROVED_X10a')==1
core=core.replace('LOCAL_AUTHOR_APPROVED_X10a','LOCAL_AUTHOR_APPROVED_X11')
put(D/'core.py',core)
proof=dict(original_core_sha256=hashlib.sha256((S/'ce_driver.py').read_bytes()).hexdigest(),
    extracted_functions=names,all_functions_literal_identity_except_receipt_execution_label=True,
    original_constructor_sha256=hashlib.sha256((S/'s_ce_original.py').read_bytes()).hexdigest(),rectangular_edits=edits,
    unchanged_prefix_collector=True,unchanged_engine=True)
put(R/'SOURCE_IDENTITY_v1.json',json.dumps(proof,indent=2))
pairs=sorted(set([(48,m) for m in [4,6,8,12,16,24,32]]+[(n,16) for n in [24,32,48,64,96]]))
cfg=dict(experiment='X11',execution='LOCAL_AUTHOR_APPROVED_X11',review_sha256=review,
    cells=[dict(n=n,m=m,prefixes=[2048,8192,32768,131072,524288]+([1048576] if n+m>=120 else [])) for n,m in pairs],
    systems=list(range(301,309)),seeds=list(range(1601,1605)),workers=4,blas_threads=1,
    pilot_cases=[dict(n=48,m=48,system=9911,seed=7711,prefixes=[2048,8192]),
      dict(n=48,m=4,system=9912,seed=7712,prefixes=[2048,8192]),
      dict(n=96,m=16,system=9913,seed=7713,prefixes=[2048,8192,32768,131072,524288])],
    pilot_checks=['square_model_bitwise','all_rectangular_shapes_rank_and_certificate','original_generic_CE_fit_gain_metric_RNG_count_bitwise',
      'one_BLAS_thread','peak_working_set_below_2GiB','available_memory_above_4GiB','free_disk_above_5GiB'],
    formal_paths=len(pairs)*32,formal_transitions=sum((max(x['prefixes'])+512)*32 for x in [dict(n=n,m=m,prefixes=[2048,8192,32768,131072,524288]+([1048576] if n+m>=120 else [])) for n,m in pairs]),
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in D.iterdir() if p.is_file()},
    driver_sha256=hashlib.sha256((R/'run_x11.py').read_bytes()).hexdigest(),Grace_SU=0,retry_limit=0)
put(R/'config-v1.json',json.dumps(cfg,indent=2))
protocol='''# X11 CE rectangular one-factor sweeps

Author GO 13:15 CDT Nov6. Construction issue reported before numerical work in
CONSTRUCTION_NOTICE_v1.md and CODEX_REPLY. Minimal rectangular extension is
specified there; all square inputs reproduce the exact old constructor.
Family S, rank2,Q=W=I_n,R=I_m,K0=0,pbar2. All streams, CE burn512,
continuous nested prefix collector, same-data OLS, dense and rank2 learner
preserved. Formal systems301..308,seeds1601..1604.

Sweep M: n48,m4/6/8/12/16/24/32; reuse old square48 by reference.
Sweep N: m16,n24/32/48/64/96; reuse X10a square16 by reference.
Cell(48,16) is collected once. All11 new cells use2048,8192,32768,131072,524288;
the fixed append rule n+m>=120 applies to none of these new cells.
352physical paths,184729600transitions;0GraceSU. Four local workers, one
BLAS/Numba thread each, existing E Python environment. Output/cache/temp
inside this new E namespace. No installation. Preserve every failure as+inf.

PILOT fixed before work: three disjoint new cases in config; original model
square byte equality; all requested rectangular dimensions/rank/certificate;
fit/gain/metric/RNG/count bitwise comparison to original generic CE for each
pilot case; one thread; peakRSS<2GiB; availableRAM>4GiB; freeE>5GiB.
No outcome/stability/efficacy selection. Stop/report on any failed check.
FORMAL follows automatically iff every fixed check passes and review unchanged.

REPORT uses original X6a/X10a absolute eps.01, median32 gaps at eachN,
first log-log downcross interpolation, no extrapolation and left/right
censor flags. Sample-cost schema n,eps,dense_N_req,truncated_N_req plus m;
write new rows and merged reuse square48/16 with source SHA provenance.
Report paired dense/trunc gap ratios at everyN (seed median then system
median, all32denominator, both-stable and failure-inclusive counts), all
stable/failure counts and raw records. Descriptive, no theorem verification.
Old results/paper read only. No retry. Recheck review before every advancement.
'''
put(R/'PROTOCOL_v1.md',protocol)
with (C/'CODEX_REPLY.md').open('a',encoding='utf-8') as f:
    f.write('\n## X11 PROTOCOL\n\n'+protocol+'\nConfig/source hashes in config-v1.json and SOURCE_IDENTITY_v1.json.\nSTATUS: PROTOCOL DONE X11\n')
print(json.dumps(dict(status='PROTOCOL_FROZEN',cells=len(pairs),paths=cfg['formal_paths'],transitions=cfg['formal_transitions'],Grace_SU=0)))
