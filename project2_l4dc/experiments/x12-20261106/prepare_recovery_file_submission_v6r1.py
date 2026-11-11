"""Materialize the registered wrap bodies as script files; no science changes."""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath


R = Path(__file__).resolve().parent
REVIEW = R.parents[1] / 'CLAUDE_TASK.md'
DEPLOYED_HELPER_SHA = '2ac81aade4027497cc03415a3ec723bac12abf546ffa1b8b34009e7053a9492b'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def change(s, a, b, count=1):
    assert s.count(a) == count, a
    return s.replace(a,b)


def main(a):
    review = REVIEW.read_bytes()
    assert sha(review) == a.expected_review_sha256
    release = json.loads((R/'recovery-release-v6/RELEASE_MANIFEST_v5.json').read_bytes())
    assert sha((R/'recovery-release-v6/recovery-config.json').read_bytes()) == release['config_sha256']
    assert sha((R/'recovery-release-v6/recovery-v5.zip').read_bytes()) == release['bundle_sha256']
    root = PurePosixPath(release['remote_root'])
    assert str(root) == '/scratch/user/changze/lqr_experiments/tmp/x12-storage-recovery-20261107-v6'
    original = (R/'submit_recovery_v5.py').read_bytes()
    assert sha(original) == DEPLOYED_HELPER_SHA
    source = original.decode()
    source = change(source, 'def wrap(root, mode, group=None):', 'def script_body(root, release, mode, group=None):')
    source = change(source, "    release = read(root/'RECOVERY_RELEASE_MANIFEST_v5.json')\n", '')
    source = change(source, "    args += ['--wrap',wrap(root,mode,group)]",
                    "    script=root/f'recovery-v6r1-{role}.sbatch'\n"
                    "    expected='#!/usr/bin/env bash\\n'+script_body(root,read(root/'RECOVERY_RELEASE_MANIFEST_v5.json'),mode,group)\n"
                    "    assert script.read_bytes()==expected.encode()\n"
                    "    args.append(str(script))")
    source = change(source, 'x12-rec-v5-', 'x12-rec-v6r1-', count=2)
    source = change(source, 'RECOVERY_FORMAL_SUBMITTED_v5.json', 'RECOVERY_FORMAL_SUBMITTED_v6r1.json', count=2)
    source = change(source, "    if a.stage in ('preflight','formal'):\n",
                    "    if a.stage in ('preflight','formal'):\n"
                    "        rejection=read(ROOT/'x12-rec-v5-npg-RESPONSE.json')\n"
                    "        assert not rejection['stdout'].strip() and 'Script arguments not permitted with --wrap option' in rejection['stderr']\n"
                    "        assert not (ROOT/'x12-rec-v5-npg-DONE.json').exists() and not (ROOT/'x12-rec-v5-pi-BEGIN.json').exists()\n"
                    "        assert not call(['sacct','-X','--array','-n','-P','-u',USER,'-S',START,'--name=x12-rec-v5-npg,x12-rec-v5-pi','--format=JobID']).strip()\n"
                    "        assert not any(ROOT.glob('n60-nine-*-task-*.tar'))\n")
    # The helper has only constant definitions and functions under this name.
    ns={'__name__':'_prepare_recovery_submit'}
    exec(compile(ast.parse(source), 'submit_recovery_v6r1.py', 'exec'),ns)
    files={'submit_recovery_v6r1.py':source.encode()}
    for role,mode,group in [('npg','formal','n60-nine-NPG'),('pi','formal','n60-nine-PI'),('report','report',None)]:
        body=ns['script_body'](root,release,mode,group)
        files[f'recovery-v6r1-{role}.sbatch']=('#!/usr/bin/env bash\n'+body).encode()
    hashes={n:sha(b) for n,b in files.items()}
    if a.validate_only:
        print(json.dumps(dict(status='FILE_BASED_SUBMISSION_SYNTAX_PASS', hashes=hashes)))
        return
    assert (R/'recovery-v6-interface-stop-v1/REJECTION_VERIFIED.json').is_file()
    assert REVIEW.read_bytes()==review
    out=R/'recovery-submit-v6r1'
    out.mkdir()
    for n,b in files.items():
        with (out/n).open('xb') as f:f.write(b)
    result=dict(status='FORMAL_SCRIPT_INTERFACE_PREPARED_NOT_SUBMITTED', remote_root=str(root),
                hashes=hashes, prior_helper_sha256=DEPLOYED_HELPER_SHA, review_sha256=sha(review),
                unchanged_config_sha256=release['config_sha256'], unchanged_bundle_sha256=release['bundle_sha256'],
                new_cpu_SU=0, new_training_transitions=0)
    with (out/'PREPARED.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--expected-review-sha256',required=True)
    p.add_argument('--validate-only',action='store_true');main(p.parse_args())
