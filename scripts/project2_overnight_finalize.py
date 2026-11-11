"""Cost reconciliation and checksum archive; read own job IDs only."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import time

BASE=Path('/scratch/user/changze/lqr_experiments')
OUT=BASE/'results/project2-overnight-20261020'


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def main():
    main_done=json.loads((OUT/'completion.json').read_text())
    extra=json.loads((OUT/'high-budget/report/summary.json').read_text())
    assert main_done['audit']['status']=='PASS' and extra['status']=='complete'
    derived=json.loads((OUT/'derived/summary.json').read_text())
    assert derived['status']=='PASS'
    ids=['20220238','20220239','20220240','20220343','20220344','20220440','20220552','20220623','20220625']
    ids.append((OUT/'submission-derived.txt').read_text().strip())
    ids.append((OUT/'submission-publication.txt').read_text().strip())
    assert json.loads((OUT/'publication/figure_receipt.json').read_text())['status']=='complete'
    txt=subprocess.check_output(['sacct','-j',','.join(ids),'-n','-P',
        '--format=JobIDRaw,JobID,State,ElapsedRaw,AllocCPUS,AllocTRES,MaxRSS'],universal_newlines=True)
    account=OUT/'accounting';account.mkdir(exist_ok=True)
    (account/'own_jobs.psv').write_text(txt)
    jobs=[];maxrss=[]
    for line in txt.splitlines():
        cells=line.split('|')
        if len(cells)<7 or not cells[0]:continue
        if '.' not in cells[1]:
            jobs.append(dict(raw_id=cells[0],job_id=cells[1],state=cells[2],elapsed_seconds=int(cells[3] or 0),
                allocated_CPUs=int(cells[4] or 0),allocated_TRES=cells[5]))
        if cells[6]:maxrss.append(dict(job_id=cells[1],MaxRSS=cells[6]))
    assert jobs and all(j['state']=='COMPLETED' for j in jobs),jobs
    wanted={j['raw_id'] for j in jobs};ams=[]
    allams=subprocess.check_output(['myproject','-j','132685389143'],universal_newlines=True)
    for line in allams.splitlines():
        c=[v.strip() for v in line.split('|')]
        if len(c)>9 and c[1]=='132685389143' and c[2] in wanted:
            ams.append(dict(job=c[2],array_index=c[3],wall_seconds=int(c[7]),slots=int(c[8]),SU=float(c[9])))
    assert all(r['slots']==1 for r in ams)
    current=subprocess.check_output(['myproject'],universal_newlines=True)
    (account/'allocation_snapshot.txt').write_text(current)
    cost=dict(own_slurm_records=len(jobs),allocated_core_hours=sum(j['elapsed_seconds']*j['allocated_CPUs']/3600 for j in jobs),
        AMS_rounded_settled_SU=sum(r['SU'] for r in ams),AMS_settled_records=len(ams),
        AMS_unsettled_job_ids=sorted(wanted-{r['job'] for r in ams}),
        requested_total_SU_upper_bound=18.433333333333334,round_cap_SU=100,
        own_job_records=jobs,own_AMS_records=ams,MaxRSS_records=maxrss,
        logical_coverage=dict(actor=72,main_mechanism=760,additional_central_tasks=160,
            unique_main_one_step_outputs=20520,unique_additional_one_step_outputs=1440,
            old_prefix_outputs_replayed=4320),epoch=time.time())
    (account/'cost.json').write_text(json.dumps(cost,indent=2)+'\n')
    files=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name!='final_artifact_sha256.json')
    manifest={str(p.relative_to(OUT)):sha(p) for p in files}
    mp=OUT/'final_artifact_sha256.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
    archive=BASE/'exports/project2-overnight-20261020-complete.tar.gz'
    assert not archive.exists(),'Archive exists; verify and reuse instead of overwrite'
    archive.parent.mkdir(exist_ok=True)
    with tarfile.open(archive,'w:gz') as bundle:
        bundle.add(OUT,arcname=OUT.name)
    receipt=dict(status='complete',archive=str(archive),archive_bytes=archive.stat().st_size,
        archive_sha256=sha(archive),files=len(manifest),manifest_sha256=sha(mp),
        own_slurm_records=len(jobs),allocated_core_hours=cost['allocated_core_hours'],
        AMS_rounded_settled_SU=cost['AMS_rounded_settled_SU'],unsettled_records=len(cost['AMS_unsettled_job_ids']),
        epoch=time.time())
    (archive.parent/'project2-overnight-20261020-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
