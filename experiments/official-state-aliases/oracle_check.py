"""Replay released showcase observations against pinned official offline games."""
import collections
import copy
import hashlib
import json
import logging
import pathlib
import resource
import socket
import sys
import time

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import ActionInput, GameAction

ROOT = pathlib.Path(__file__).resolve().parent
resource.setrlimit(resource.RLIMIT_CPU, (110, 110))
logging.disable(logging.CRITICAL)

def no_network(*args, **kwargs):
    raise RuntimeError('Offline validation forbids network access')
socket.socket.connect = no_network

def decode_frames(data):
    flat = np.fromiter((int(x,16) for x in data['f0']), dtype=np.uint8)
    result = [flat.copy().reshape(64,64)]
    for delta in data['deltas']:
        for j in range(0,len(delta),4):
            flat[int(delta[j:j+3],16)] = int(delta[j+3],16)
        result.append(flat.copy().reshape(64,64))
    return result

def step(game, action):
    kind, _, coords = action.partition(':')
    data = {}
    if coords:
        x,y = map(int,coords.split(',')); data = {'x':x,'y':y}
    result = game.perform_action(ActionInput(id=GameAction[kind],data=data),raw=True)
    if not result.frame:
        return result, None
    return result, np.asarray(result.frame[-1],dtype=np.uint8)

def digest(frame):
    if frame is None: return None
    return hashlib.sha256(frame.tobytes()).hexdigest()

def run(stem, full, stop_index):
    started = time.perf_counter()
    data = json.loads((ROOT/(stem+'.json')).read_text())
    frames = decode_frames(data)
    arc = Arcade(operation_mode=OperationMode.OFFLINE,
                 environments_dir=str(ROOT/'official-environments'),
                 recordings_dir=str(ROOT/'oracle-recordings'),arc_api_key='')
    env = arc.make(full,seed=0)
    game = env._game
    response, current = step(game,'RESET')
    receipt = {'game_id':full,'sdk':'arc-agi==0.9.9','engine':'arcengine==0.9.3',
               'initial_frame_equal':bool(np.array_equal(current,frames[0])),
               'initial_frame_sha256':digest(current),'seed':0,'status':'RUNNING',
               'bridge_strategy':'one_missing_action_before_or_after_recorded_action',
               'oracle_calls':1,'recorded_actions_executed':0,'bridges':[],
               'aligned_frame_indices':[],'witnesses':[],
               'adapter_fallbacks':[],'executed_history':['RESET']}
    if not receipt['initial_frame_equal']:
        receipt.update(status='INITIAL_MISMATCH',different_pixels=int(np.count_nonzero(current!=frames[0])))
        return receipt
    actions = list(dict.fromkeys(['ACTION'+str(i) for i in range(1,8)] + data['acts'] + ['RESET']))
    boundaries = {mark['i'] for mark in data['level_marks']}
    saved = {}
    wanted = {741,743,749,927,931,938,941} if stem=='dc22' else {383,470}
    for i,requested in enumerate(data['acts'][:stop_index+1]):
        action=requested
        kind=requested.partition(':')[0]
        if kind not in ('RESET','ACTION6') and GameAction[kind].value not in game._available_actions:
            action='ACTION1'
            receipt['adapter_fallbacks'].append({'i':i,'requested':requested,'executed':action})
        assert np.array_equal(current,frames[i]), 'Internal prefix alignment error'
        if i in wanted:
            saved[i] = copy.deepcopy(game)
            receipt['aligned_frame_indices'].append(i)
        pre_action_game = copy.deepcopy(game)
        effective_sequence=[action]
        response,current = step(game,action)
        receipt['oracle_calls'] += 1
        receipt['recorded_actions_executed'] += 1
        if not np.array_equal(current,frames[i+1]):
            mismatch = {'after_recorded_action_i':i,'action':action,
                        'next_is_level_boundary':i+1 in boundaries,
                        'engine_state':response.state.name,'engine_levels_completed':response.levels_completed,
                        'different_pixels':int(np.count_nonzero(current!=frames[i+1])),
                        'expected_frame_sha256':digest(frames[i+1]),'actual_frame_sha256':digest(current)}
            # Display deltas can cross an omitted action BEFORE the next retained action.
            # All calls are counted. Accept a bridge only when every pixel matches.
            hit = None
            for bridge in actions:
                alternative = copy.deepcopy(pre_action_game)
                first, ff=step(alternative,bridge)
                if ff is None:
                    receipt['oracle_calls']+=1; continue
                br,bf=step(alternative,action)
                receipt['oracle_calls'] += 2
                if np.array_equal(bf,frames[i+1]):
                    hit = (alternative,br,bf,bridge,'before'); break
            if hit is None:
                for bridge in actions:
                    alternative = copy.deepcopy(game)
                    br, bf = step(alternative,bridge); receipt['oracle_calls'] += 1
                    if np.array_equal(bf,frames[i+1]):
                        hit = (alternative,br,bf,bridge,'after'); break
            if hit is None:
                receipt.update(status='UNALIGNED',mismatch=mismatch)
                break
            game,response,current,bridge,placement = hit
            effective_sequence=([bridge,action] if placement=='before' else [action,bridge])
            mismatch.update(inserted_actions=[bridge],aligned=True,
                            insertion=placement,
                            aligned_levels_completed=response.levels_completed)
            receipt['bridges'].append(mismatch)
        receipt['executed_history'].extend(effective_sequence)
        if i in {25,93,141,204,645,741,749,941}:
            print(json.dumps({'progress_i':i,'levels':response.levels_completed,'oracle_calls':receipt['oracle_calls']}),flush=True)
    else:
        receipt['status']='PREFIX_ALIGNED'
    if 741 in saved:
        origin=saved[741]
        selection='ACTION6:51,46'
        selected=copy.deepcopy(origin)
        sr,sf=step(selected,selection);receipt['oracle_calls']+=1
        same=bool(np.array_equal(sf,frames[741]))
        for suffix in ['ACTION2','ACTION4','ACTION6:48,23']:
            a=copy.deepcopy(origin);b=copy.deepcopy(selected)
            ar,af=step(a,suffix);br,bf=step(b,suffix);receipt['oracle_calls']+=2
            item={'origin_recorded_frame_i':741,'selection_action':selection,
                  'selection_leaves_observation_equal':same,'suffix':suffix,
                  'different_pixels':int(np.count_nonzero(af!=bf)),
                  'without_selection_state':ar.state.name,'with_selection_state':br.state.name,
                  'without_selection_levels':ar.levels_completed,'with_selection_levels':br.levels_completed,
                  'without_selection_frame_sha256':digest(af),'with_selection_frame_sha256':digest(bf)}
            receipt['witnesses'].append(item)
    pairs=[(743,749),(927,931),(938,941)] if stem=='dc22' else [(383,470)]
    receipt['recorded_alias_checks']=[]
    for first,second in pairs:
        if first not in saved or second not in saved:continue
        action=data['acts'][first]
        assert action==data['acts'][second]
        ar,af=step(copy.deepcopy(saved[first]),action);br,bf=step(copy.deepcopy(saved[second]),action)
        receipt['oracle_calls']+=2
        receipt['recorded_alias_checks'].append({'indices':[first,second],'action':action,
            'same_observed_frame':bool(np.array_equal(frames[first],frames[second])),
            'different_official_successor_pixels':int(np.count_nonzero(af!=bf)),
            'first_official_matches_recorded':bool(np.array_equal(af,frames[first+1])),
            'second_official_matches_recorded':bool(np.array_equal(bf,frames[second+1]))})
    receipt['elapsed_seconds']=time.perf_counter()-started
    receipt['action_search_candidates']=len(actions)
    return receipt

if __name__=='__main__':
    stem=sys.argv[1]; full={'dc22':'dc22-fdcac232','sp80':'sp80-589a99af'}[stem]
    result=run(stem,full,int(sys.argv[2]) if len(sys.argv)>2 else (942 if stem=='dc22' else 471))
    (ROOT/(stem+'-oracle-replay-result.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
