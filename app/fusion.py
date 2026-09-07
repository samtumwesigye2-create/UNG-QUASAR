from __future__ import annotations
import requests, time
from datetime import datetime, timezone
from . import history, health

_state={'satellites':{},'aircraft':{},'vessels':{},'last_updated':None,'correlations':[],'entities':[]}

def get_state(): return _state

def _prov(source='ARGUS',station_id='default',confidence=1.0): return {'source':source,'station_id':station_id,'received_at':datetime.now(timezone.utc).isoformat(),'confidence':float(confidence)}
def _headers():
    import os
    key=os.getenv('ARGUS_API_KEY','').strip(); h={}
    if key: h['X-ARGUS-API-Key']=key
    return h

def _argus_get(url,path,params=None):
    try:
        r=requests.get(f"{url.rstrip('/')}{path}",params=params,headers=_headers(),timeout=8); r.raise_for_status(); return r.json()
    except Exception: return None

def _freshen(obj,station_id):
    d=dict(obj); d['_provenance']=_prov('ARGUS',station_id,d.get('confidence',1.0)); return d

async def collect_cycle(argus_url,tracked_satellites,station_id='default'):
    start=time.perf_counter(); successes=0
    for name in tracked_satellites:
        d=_argus_get(argus_url,'/api/track',{'name':name,'station_id':station_id})
        if d and d.get('name'):
            d=_freshen(d,station_id); _state['satellites'][d['name']]=d; await history.record_satellite(d,station_id); successes+=1
    ad=_argus_get(argus_url,'/api/geoint/aircraft')
    if ad and not ad.get('error'):
        items=[_freshen(x,station_id) for x in ad.get('aircraft',[]) if x.get('icao')]
        for a in items: _state['aircraft'][a['icao']]=a
        await history.record_aircraft(items,station_id); successes+=1
    vd=_argus_get(argus_url,'/api/geoint/ships')
    if vd:
        items=[_freshen(x,station_id) for x in vd.get('ships',[]) if x.get('mmsi') is not None]
        for v in items: _state['vessels'][str(v['mmsi'])]=v
        await history.record_vessels(items,station_id); successes+=1
    _state['last_updated']=datetime.now(timezone.utc).isoformat(); health.mark_collection(successes>0,(time.perf_counter()-start)*1000,None if successes else 'No ARGUS feeds returned data')
    return successes

def mark_stale(stale_after_s=120):
    now=datetime.now(timezone.utc)
    for bucket in ('satellites','aircraft','vessels'):
        for obj in _state[bucket].values():
            try:
                ts=datetime.fromisoformat(obj.get('_provenance',{}).get('received_at').replace('Z','+00:00')); obj['_stale']=(now-ts).total_seconds()>stale_after_s
            except Exception: obj['_stale']=True
