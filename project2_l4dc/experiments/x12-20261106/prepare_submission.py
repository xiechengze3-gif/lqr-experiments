from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent;C=R.parents[1]
m=json.loads((R/'PROTOCOL_MANIFEST_v1.json').read_text());sha=hashlib.sha256
review=sha((C/'CLAUDE_TASK.md').read_bytes()).hexdigest();assert review==m['review_sha256']
s=(R/'submit_calibration_v1.py').read_text().replace('__CONFIG_SHA__',m['config_sha256'])
helper=R/'submit_calibration_frozen_v1.py'
with helper.open('xb') as f:f.write(s.encode())
runner='''$ErrorActionPreference='Stop'
if ((Get-FileHash -LiteralPath '__CHANNEL__/CLAUDE_TASK.md' -Algorithm SHA256).Hash.ToLowerInvariant() -ne '__REVIEW__') {throw 'Review changed; reread before pilot.'}
$q=@'
python3 -c "from pathlib import Path; b=Path('/scratch/user/changze/lqr_experiments'); assert not (b/'tmp/x12-20261106').exists(); assert not (b/'results/x12-20261106').exists(); assert not (b/'releases/x12-20261106-pilot-v1').exists(); (b/'tmp/x12-20261106').mkdir(); print('NEW_X12_PATHS_PASS')"
'@
& 'E:/ChatGPT/Tools/Grace/Invoke-Grace.ps1' -NormalWindowsUserContext -Command $q
& 'E:/ChatGPT/Cache/putty/0.85/pscp.exe' -load Grace-Codex-Downstream -batch -share -sftp -q '__ARCHIVE__' '__HELPER__' 'changze@grace.hprc.tamu.edu:/scratch/user/changze/lqr_experiments/tmp/x12-20261106/'
if ($LASTEXITCODE -ne 0) {throw 'Upload response uncertain; reconcile before replay.'}
$q=@'
python3 - <<'PY'
import hashlib,tarfile
from pathlib import Path
b=Path('/scratch/user/changze/lqr_experiments');p=b/'tmp/x12-20261106/x12-20261106-pilot-v1.tar.gz'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='__ARCHIVE_SHA__'
helper=b/'tmp/x12-20261106/submit_calibration_frozen_v1.py'
assert hashlib.sha256(helper.read_bytes()).hexdigest()=='__HELPER_SHA__'
with tarfile.open(p) as tf:
 for item in tf.getmembers():
  path=Path(item.name);assert item.isfile() and not path.is_absolute() and '..' not in path.parts and path.parts[0]=='x12-20261106-pilot-v1'
 tf.extractall(b/'releases')
exec(compile(helper.read_text(),str(helper),'exec'))
PY
'@
$result=(& 'E:/ChatGPT/Tools/Grace/Invoke-Grace.ps1' -NormalWindowsUserContext -Command $q) -join "`n"
[IO.File]::WriteAllText('__RESPONSE__',$result,[Text.UTF8Encoding]::new($false))
$result
'''
values={'__CHANNEL__':C.as_posix(),'__REVIEW__':review,'__ARCHIVE__':(R/'x12-20261106-pilot-v1.tar.gz').as_posix(),'__HELPER__':helper.as_posix(),
    '__ARCHIVE_SHA__':m['archive_sha256'],'__HELPER_SHA__':sha(helper.read_bytes()).hexdigest(),'__RESPONSE__':(R/'calibration-submission-response-v1.json').as_posix()}
for key,value in values.items():runner=runner.replace(key,value)
with (R/'Submit-Calibration-v1.ps1').open('xb') as f:f.write(runner.encode())
print(json.dumps(dict(status='SUBMISSION_PREPARED',review_sha256=review,requested_SU=2.75)))
