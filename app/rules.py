from __future__ import annotations
import hashlib, json, time

_last_fired={}

def fingerprint(category,subject,data):
    stable=json.dumps(data or {},sort_keys=True,default=str)
    return hashlib.sha256(f'{category}|{subject}|{stable}'.encode()).hexdigest()[:24]

def should_emit(category,subject,data,cooldown_s:int=300):
    fp=fingerprint(category,subject,data); now=time.time(); prev=_last_fired.get(fp,0)
    if now-prev < cooldown_s: return False,fp
    _last_fired[fp]=now; return True,fp
