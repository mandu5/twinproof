"""Validate bounded model plans from a fully replayed official dc22 state."""
import copy
import hashlib
import json
import pickle
import time
import numpy as np
from oracle_check import ROOT, Arcade, OperationMode, decode_frames, step, digest

started=time.perf_counter()
payload=json.loads((ROOT/'dc22.json').read_text());frames=decode_frames(payload)
prefix=json.loads((ROOT/'dc22-reset-prefix-to-frame743.json').read_text())
arc=Arcade(operation_mode=OperationMode.OFFLINE,environments_dir=str(ROOT/'official-environments'),arc_api_key='')
game=arc.make(prefix['game_id'],seed=prefix['seed'])._game
for action in prefix['actions']:response,current=step(game,action)
root=copy.deepcopy(game)
receipt={'game_id':prefix['game_id'],'sdk':'arc-agi==0.9.9','engine':'arcengine==0.9.3',
         'root_frame_i':743,'target_frame_i':750,'root_reached_from_full_reset':True,
         'root_frame_equal':bool(np.array_equal(current,frames[743])),
         'root_frame_sha256':digest(current),'prefix_oracle_calls':len(prefix['actions']),
         'root_engine_state':response.state.name,'root_levels_completed':response.levels_completed,
         'validations':[],'branch_oracle_calls':0}
assert receipt['root_frame_equal']
try:
    blob=pickle.dumps(root,protocol=5)
    (ROOT/'dc22-official-root743.pkl').write_bytes(blob)
    receipt['local_engine_snapshot']={'file':'dc22-official-root743.pkl','bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}
except (pickle.PickleError,TypeError,AttributeError) as exc:
    receipt['local_engine_snapshot']={'status':'NOT_SERIALIZABLE','reason':str(exc),'portable_reconstruction':'dc22-reset-prefix-to-frame743.json'}
for arm in ['grid','full','refined']:
    plan=json.loads((ROOT/('dc22-plan-'+arm+'.json')).read_text())['result']
    if plan['status']!='FOUND':
        receipt['validations'].append({'arm':arm,'status':plan['status']});continue
    branch=copy.deepcopy(root)
    for action in plan['path']:response,current=step(branch,action);receipt['branch_oracle_calls']+=1
    receipt['validations'].append({'arm':arm,'path':plan['path'],
        'official_target_frame_equal':bool(np.array_equal(current,frames[750])),
        'different_target_pixels':int(np.count_nonzero(current!=frames[750])),
        'official_frame_sha256':digest(current),'official_state':response.state.name,
        'levels_completed':response.levels_completed})
looped=copy.deepcopy(root)
for action in prefix['return_loop']:lr,lf=step(looped,action);receipt['branch_oracle_calls']+=1
direct=copy.deepcopy(root)
ar,af=step(direct,prefix['distinguishing_suffix'][0]);br,bf=step(looped,prefix['distinguishing_suffix'][0]);receipt['branch_oracle_calls']+=2
receipt['return_loop_witness']={'actions':prefix['return_loop'],
    'exact_return_to_root_grid':bool(np.array_equal(lf,frames[743])),
    'suffix':prefix['distinguishing_suffix'],
    'different_official_successor_pixels':int(np.count_nonzero(af!=bf)),
    'direct_matches_recorded744':bool(np.array_equal(af,frames[744])),
    'looped_matches_recorded750':bool(np.array_equal(bf,frames[750]))}
receipt['elapsed_seconds']=time.perf_counter()-started
(ROOT/'dc22-plan-official-validation.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
