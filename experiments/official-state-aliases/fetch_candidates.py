"""Download published candidates by verified hash; source stays in local cache."""
import hashlib
import pathlib
import subprocess

ROOT=pathlib.Path(__file__).resolve().parent
PINNED={
    'dc22':'6355c9d669b989ffb3f1acea9e1a101e2e655ccfc3bd6df1d8bfadb860401253',
    'sp80':'6d9e2562a3ac8c10f0a6969356ffc14b985d5f1a5628a925d808ab0f76638818',
}
for stem,expected in PINNED.items():
    url='https://arc-agi-3-twin.vercel.app/games/'+stem+'.json'
    raw=subprocess.check_output(['curl','--fail','--silent','--show-error','--max-time','25','--max-filesize','1500000',url])
    actual=hashlib.sha256(raw).hexdigest()
    if actual!=expected:raise RuntimeError('Published candidate changed: '+stem+' expected '+expected+' received '+actual)
    (ROOT/(stem+'.json')).write_bytes(raw)
    print(stem,len(raw),actual)
