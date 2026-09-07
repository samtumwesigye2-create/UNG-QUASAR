from __future__ import annotations

def select_station(stations:list[dict], required_capabilities:list[str]|None=None):
    req=set(required_capabilities or [])
    candidates=[]
    for s in stations:
        caps=set(s.get('capabilities') or [])
        if not req.issubset(caps): continue
        if not s.get('online',True): continue
        score=float(s.get('visibility_score',0))*0.45 + (100-float(s.get('load_pct',0)))*0.25 + float(s.get('link_quality',50))*0.2 + float(s.get('priority',50))*0.1
        candidates.append((score,s))
    if not candidates: return None
    candidates.sort(key=lambda x:x[0],reverse=True)
    return {'score':round(candidates[0][0],2),'station':candidates[0][1]}
