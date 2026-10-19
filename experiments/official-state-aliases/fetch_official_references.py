"""Fetch exact public references locally; never redistribute downloaded sources."""
import ast
import datetime
import hashlib
import json
import pathlib
import subprocess

ROOT=pathlib.Path(__file__).resolve().parent
PINNED={
    'dc22-fdcac232':'74abe3523bd6bc8a0948991caa0ca71855e38542ba2123653a03485e064f252e',
    'sp80-589a99af':'2306d62311a3cc027250217d86cb4e012898edc7647a7c291ade23f36c9b9715',
}

def get(path,key=None):
    args=['curl','--fail','--silent','--show-error','--max-time','25','--max-filesize','1500000']
    if key:args += ['--header','@-']
    args += ['https://three.arcprize.org'+path]
    return subprocess.check_output(args,input=(('X-Api-Key: '+key+'\n').encode() if key else None),stderr=subprocess.PIPE)

key=json.loads(get('/api/games/anonkey'))['api_key']
receipts=[]
for full,expected in PINNED.items():
    meta=json.loads(get('/api/games/'+full,key));assert meta['game_id']==full
    source=get('/api/games/'+full+'/source',key)
    actual=hashlib.sha256(source).hexdigest()
    if actual!=expected:raise RuntimeError('Pinned source changed: '+full+' expected '+expected+' received '+actual)
    ast.parse(source)
    stem,version=full.split('-',1);dest=ROOT/'official-environments'/stem/version
    dest.mkdir(parents=True,exist_ok=True)
    meta['class_name']=meta.get('class_name') or stem.capitalize()
    meta['date_downloaded']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    meta['local_dir']=str(dest);meta.setdefault('tags',[]);meta.setdefault('baseline_actions',[])
    (dest/'metadata.json').write_text(json.dumps(meta,indent=2))
    (dest/(meta['class_name'].lower()+'.py')).write_bytes(source)
    receipts.append({'game_id':full,'source_bytes':len(source),'source_sha256':actual,'metadata':meta})
print(json.dumps(receipts,indent=2))
