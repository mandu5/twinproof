"""One bounded, exposed constructed target task on the unchanged dc22 model."""
import hashlib
import json
import os
import pathlib
import resource
import sys
import time

ROOT=pathlib.Path(__file__).resolve().parent
DEFAULT_REPO=ROOT/'method' if (ROOT/'method/src/twinproof').is_dir() else ROOT.parent.parent
REPO=pathlib.Path(os.environ.get('TWINPROOF_REPO',str(DEFAULT_REPO))).resolve()
sys.path.insert(0,str(REPO/'src'))
from twinproof.world_model import PythonModel, decode_showcase, state_key
from twinproof.world_audit import bounded_search

resource.setrlimit(resource.RLIMIT_CPU,(90,90))
arm=sys.argv[1]
data=json.loads((ROOT/'dc22.json').read_text());rows=decode_showcase(data)
model=PythonModel(data['model']['src'])
for row in rows[:743]:model.predict(row.before,row.action)
snapshot=model.snapshot();grid=rows[743].before;target=rows[749].after
actions=['ACTION6:52,25','ACTION2','ACTION6:49,46','ACTION1']
fields={'grid':[],'full':None,'refined':['_level6_pair','_ambiguous_x10_38_calls']}[arm]
result=bounded_search(model,grid,snapshot,actions,target,fields=fields,max_depth=7,max_expansions=1000)
receipt={'arm':arm,'game':'dc22','root_recorded_frame_i':743,'target_recorded_frame_i':750,
         'scope':'constructed exposed reachability task; no game-win claim',
         'actions':actions,'max_depth':7,'max_expansions':1000,'teacher_forced_prefix_calls':743,
         'snapshot_fields':sorted(snapshot),'key_fields':fields,'root_key':state_key(grid,snapshot,fields),
         'source_sha256':hashlib.sha256(data['model']['src'].encode()).hexdigest(),
         'implementation_sha256':{name:hashlib.sha256((REPO/'src/twinproof'/name).read_bytes()).hexdigest() for name in ['world_model.py','world_audit.py']},
         'result':result}
(ROOT/('dc22-plan-'+arm+'.json')).write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2),flush=True)
