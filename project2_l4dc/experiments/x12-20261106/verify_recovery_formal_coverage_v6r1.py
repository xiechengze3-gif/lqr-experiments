"""Reconcile all completed Slurm allocations with the E task proofs and work plan."""
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

from recovery_driver_v5 import NEW, OLD
from virtual_task_store_v2 import file_sha


def main():
    r=Path(__file__).resolve().parent
    folder=r/'delivery-recovery-tasks-v6r1'
    release=json.loads((r/'recovery-release-v6/RELEASE_MANIFEST_v5.json').read_bytes())
    bundle=r/'recovery-release-v6/recovery-v5.zip'
    assert file_sha(bundle)==release['bundle_sha256']
    with zipfile.ZipFile(bundle) as z:
        plan=json.loads(z.read('recovery-membership.json'))
    snapshot_path=sorted(folder.glob('STATE-*.json'))[-1]
    snapshot=json.loads(snapshot_path.read_bytes())
    rows=snapshot['rows']
    assert len(rows)==64 and not snapshot['failures']
    assert all(row['state']=='COMPLETED' and row['exitcode']=='0:0' and {'billing=1','cpu=1'}<=set(row['allocation'].split(',')) for row in rows)
    lookup={(x['algorithm'],x['index']):x for x in rows}
    remote={x['key']:x for x in snapshot['completed']}
    assert len(lookup)==len(remote)==64
    assert len(list(folder.glob('*.verified.json')))==64
    assert {t['origin'] for x in plan['tasks'] for t in x['runs']}=={OLD,NEW}
    accepted=Counter()
    counts=Counter()
    for t in plan['tasks']:
        idx,alg=t['index'],t['algorithm']
        key=f"{t['group']}-task-{idx:02d}"
        p=json.loads((folder/(key+'.verified.json')).read_bytes())
        assert p['status']=='TASK_ARCHIVE_AND_MEMBERS_VERIFIED_ON_E' and p['key']==key
        assert p['config_sha256']==release['config_sha256']
        assert p['job']==lookup[alg,idx]['job']==remote[key]['job']
        assert p['archive_sha256']==remote[key]['archive_sha256'] and p['journal_sha256']==remote[key]['journal_sha256']
        assert len(p['paths'])==len(t['runs'])==9
        expected=Counter()
        for result,work in zip(p['paths'],t['runs']):
            assert all(result[k]==work[k] for k in ('rung','algorithm','primitive_per_arm','origin'))
            assert result['path']==alg+'-'+work['rung_label'] and re.fullmatch('[0-9a-f]{64}',result['done_sha256'])
            if work['origin']==OLD:
                assert result['done_sha256']==work['done_sha256'] and result['final_stable']==work['final_stable']
            expected[work['origin']]+=2*work['primitive_per_arm']
            counts[work['origin']]+=1
        assert expected==p['accepted_transitions']
        accepted.update(expected)
    assert counts==plan['counts']=={OLD:296,NEW:280}
    assert accepted==plan['transitions']=={OLD:9476201216,NEW:184168537344}
    result=dict(status='ALL64_FORMAL_COMPLETED_AND_RAW_VERIFIED_ON_E',job_ids=snapshot['jobs'],task_allocations=64,
                paired_paths=sum(counts.values()), counts=counts, training_transitions_by_origin=accepted,
                logical_transitions=sum(accepted.values()), actual_formal_SU=sum(x['elapsed_seconds'] for x in rows)/3600,
                config_sha256=release['config_sha256'], state_snapshot=str(snapshot_path),state_sha256=file_sha(snapshot_path),
                reused_archive_sha256=plan['reused_archive_sha256'], no_mid_path_resume=True)
    with (r/'RECOVERY_FORMAL_COVERAGE_v6r1.json').open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2)
    print(json.dumps(result))


if __name__=='__main__':main()
