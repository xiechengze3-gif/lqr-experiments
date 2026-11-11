"""Plan disjoint E copies from completed task metadata; never packs/submits."""
import argparse,hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(a):
    status=load(a.status);assert status['status']=='X12_READONLY_METADATA_STATUS'
    assert not status['uncertain_reservations'],'Reconcile reservations first.'
    if (R/'FULL_RAW_E_COVERAGE_v1.json').exists():
        d=load(R/'FULL_RAW_E_COVERAGE_v1.json');assert d['paired_paths']==576
        print(json.dumps(dict(status='FULL_AUTHORITATIVE_E_RAW_ALREADY_COMPLETE',new_copies=[])));return
    verified=set();reserved=set();pending=[]
    for p in (R/'raw-deliveries-v1').glob('*.verified.json'):
        v=load(p)
        if v['scope']!='formal-completed':continue
        assert v['status']=='VERIFIED_EXTRACTED_COMPLETE_X12_RAW_SNAPSHOT'
        manifest=R/'raw-downloads-v1'/('x12-raw-'+v['label']+'.tar.json');assert sha(manifest)==v['manifest_sha256']
        m=load(manifest);assert m['status']=='SEALED_COMPLETE_X12_RAW_SNAPSHOT'
        assert re.fullmatch(r'n60-nine-(NPG|PI)',m['group'])
        indices=[int(x) for x in m['indices'].split(',')];assert 1<=len(indices)<=8
        folder=R/'raw-deliveries-v1'/v['label'];lookup={x['path']:x['sha256'] for x in m['files']}
        for index in indices:
            name='formal-v1/'+m['group']+'/task-'+str(index)+'/DONE.json';done=load(folder/name)
            assert sha(folder/name)==lookup[name] and done['status']=='COMPLETE' and done['index']==index
            assert len(done['paths'])==9 and done['group']['id']==m['group'];verified.add((m['group'],index))
    for p in R.glob('RAW_REMOTE_SEAL_*.json'):
        d=load(p)
        if d['scope']!='formal-completed':continue
        for i in map(int,d['indices'].split(',')):
            key=(d['group'],i);reserved.add(key)
            if key not in verified:pending.append(dict(group=key[0],index=i,seal=str(p),action='Resume existing sealed archive/manifest copy only; do not repack.'))
    plans=[]
    for alg,progress in status['formal_groups'].items():
        assert alg in ['NPG','PI'] and not progress['hard_failures']
        group='n60-nine-'+alg
        ready=[i for i in sorted(progress['complete']) if (group,i) not in verified|reserved]
        for start in range(0,len(ready),8):
            indices=ready[start:start+8];label='formal-'+alg+'-t'+'-'.join(str(i).zfill(2) for i in indices)+'-v1'
            assert not (R/'raw-downloads-v1'/('x12-raw-'+label+'.tar.gz')).exists(),'Unsealed prior transfer attempt; reconcile.'
            plans.append(dict(group=group,indices=','.join(map(str,indices)),label=label,tasks=len(indices),paired_paths=9*len(indices)))
    result=dict(status='DISJOINT_COMPLETE_TASK_COPY_PLAN',source_status_path=str(a.status),source_status_sha256=sha(a.status),
                already_verified_tasks=len(verified),reserved_tasks=len(reserved),incomplete_existing_copies=pending,
                new_copies=plans,automatic_retries=0,new_training_transitions=0)
    print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--status',required=True,type=Path);main(p.parse_args())
