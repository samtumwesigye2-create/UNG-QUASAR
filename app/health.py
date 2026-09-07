from __future__ import annotations
from datetime import datetime, timezone

_state={'started_at':datetime.now(timezone.utc).isoformat(),'last_collection_ok':None,'last_collection_error':None,'last_collection_latency_ms':None,'cycles':0,'argus_reachable':False,'last_pattern_run':None,'last_report':None}

def mark_collection(ok:bool, latency_ms:float|None=None, error:str|None=None):
    now=datetime.now(timezone.utc).isoformat(); _state['cycles']+=1
    _state['argus_reachable']=bool(ok); _state['last_collection_latency_ms']=latency_ms
    if ok: _state['last_collection_ok']=now; _state['last_collection_error']=None
    else: _state['last_collection_error']=error or 'unknown'

def mark_patterns(): _state['last_pattern_run']=datetime.now(timezone.utc).isoformat()
def mark_report(): _state['last_report']=datetime.now(timezone.utc).isoformat()
def snapshot(): return dict(_state)
