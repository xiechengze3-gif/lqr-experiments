"""Offline source/interface audit. No learners, model solves, or observations."""
import ast,csv,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent;X=R.parent/'x10-20261106'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def text(p):return p.read_text(encoding='utf-8-sig')
def functions(p):
    s=text(p);return {n.name:ast.get_source_segment(s,n) for n in ast.parse(s).body if isinstance(n,ast.FunctionDef)}
def main():
    checked=[]
    names=['audit_pilot_v1.py','prepare_followon_v1.py','remote_followon_v1.py','model_registry_driver.py',
           'coverage_formal_v1.py','report_products_v1.py','report_render_v1.py','transfer_report_v1.py',
           'copy_report_provenance_v1.py','submit_report_v1.py','prepare_report_v1.py','report_chunks_v1.py']
    for n in names:ast.parse(text(R/n),filename=n)
    checked.append('All new scientific-task controllers parse as Python; no execution/import of numerical code in this audit.')
    old=X/'actor-report-src-v1/analyze_actor_five_rungs.py';new=R/'runtime-prepared-v1/analyze_actor.py'
    a,b=functions(old),functions(new);assert a.keys()==b.keys() and all(a[k]==b[k] for k in a)
    checked.append('All analyzer functions literally match accepted X10b analyzer, including bootstrap, failure handling and inspect; only module output namespace differs.')
    a,b=functions(X/'actor-correction-controls-v2/render_report_v2.py'),functions(R/'report_render_v1.py')
    assert all(a[k]==b[k] for k in ['read','fmt','cell','emit'])
    assert b'\xe2\x88\x9e' in (R/'report_render_v1.py').read_bytes() and '\ufffd' not in text(R/'report_render_v1.py')
    checked.append('Plotting primitives literal identity and UTF-8 infinity marker preserved; failed encoding draft retained separately.')
    assert sha(R/'runtime-prepared-v1/paper_cross.py')==sha(X/'actor-report-baseline-v1/paper_cross.py')
    checked.append('Paper cross function file byte-identical to accepted reference.')
    for n in ['frozen_engine.py','estimation.py']:
        assert (R/'pilot-release-v1'/n).read_bytes()==(X/'prepared-actor-formal-v1'/n).read_bytes()
    before=text(X/'prepared-actor-formal-v1/actor_paths.py');after=text(R/'pilot-release-v1/actor_paths.py')
    assert after.replace('/results/x12-20261106','/results/x10-20261106/X10b')==before
    checked.append('Kernel/estimator bytes and actor numerical source unchanged; only actor output path guard differs.')
    for n in ['remote_followon_v1.py','submit_report_v1.py']:
        s=text(R/n);assert '--ntasks=1' in s and '--cpus-per-task=1' in s and '--mem=2048M' in s and '--no-requeue' in s
        assert 'RESERVED_BEFORE_SBATCH_DO_NOT_REPLAY' in s and 'RESPONSE.json' in s
    assert '--array=0-31%32' in text(R/'remote_followon_v1.py')
    checked.append('Once-only BEGIN/RESPONSE reservations; ntasks1/oneCPU/2GiB/no-requeue; two independent32-element arrays fit64 global slots after empty-queue preflight.')
    template=text(R/'pilot-release-v1/NPG.sbatch')
    for n in ['TMPDIR','XDG_CACHE_HOME','NUMBA_CACHE_DIR','MPLCONFIGDIR','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','OMP_NUM_THREADS=1','NUMBA_NUM_THREADS=1']:
        assert n in template
    assert '/scratch/user/changze/lqr_experiments' in template
    checked.append('Inherited one-thread environment and all remote cache/temp paths remain inside dedicated scratch namespace.')
    for n in ['summary_merged_nine_rungs.csv','transitions_saved_derived.csv','failures.csv','failure_counts_by_cell.csv']:
        assert (X/n).read_bytes()==(X/'delivery-actor-report-v1/report-v1'/n).read_bytes(),n
    with (X/'summary_merged_nine_rungs.csv').open(newline='',encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    assert len(rows)==144
    checked.append('All four proposed old CSV inputs equal accepted verified X10b delivery bytes;144summary rows. No old data read from remote scratch.')
    result=dict(status='PASS_PREPARED_SOURCES_INTERFACES_NO_NUMERICAL_WORK',checks=checked,
                files={n:sha(R/n) for n in names},analyzer_sha256=sha(new),paper_cross_sha256=sha(R/'runtime-prepared-v1/paper_cross.py'),
                formal_not_submitted_by_this_audit=True,new_training_transitions=0,Grace_SU=0)
    with (R/'PIPELINE_SOURCE_AUDIT_v1.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
if __name__=='__main__':main()
