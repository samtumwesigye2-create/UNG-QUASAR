from __future__ import annotations
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime, timezone


def haversine_km(a_lat,a_lon,b_lat,b_lon):
    try:
        R=6371.0088; p1,p2=radians(float(a_lat)),radians(float(b_lat)); dp=radians(float(b_lat)-float(a_lat)); dl=radians(float(b_lon)-float(a_lon))
        x=sin(dp/2)**2+cos(p1)*cos(p2)*sin(dl/2)**2
        return 2*R*atan2(sqrt(x),sqrt(max(0,1-x)))
    except Exception: return None

def risk_score(severity='INFO', confidence=1.0, corroboration=1, minutes_to_event=None, persistence=1):
    base={'INFO':15,'WARNING':45,'CRITICAL':75}.get(str(severity).upper(),20)
    score=base + min(15,max(0,(corroboration-1)*5)) + min(10,max(0,(persistence-1)*2))
    if minutes_to_event is not None:
        try:
            m=float(minutes_to_event); score += 10 if m<=10 else (5 if m<=30 else 0)
        except Exception: pass
    return round(max(0,min(100,score*max(.2,min(1,float(confidence))))),1)

def correlate(state:dict, max_distance_km:float=75.0):
    out=[]
    sats=state.get('satellites',{}); aircraft=state.get('aircraft',{}); vessels=state.get('vessels',{})
    for sname,s in sats.items():
        slat,slon=s.get('subpoint_lat'),s.get('subpoint_lon')
        if slat is None or slon is None: continue
        for domain,items,key in [('aircraft',aircraft,'icao'),('vessel',vessels,'mmsi')]:
            for ident,obj in items.items():
                if obj.get('lat') is None or obj.get('lon') is None: continue
                d=haversine_km(slat,slon,obj['lat'],obj['lon'])
                if d is not None and d<=max_distance_km:
                    out.append({'type':'spatiotemporal_intersection','satellite':sname,'domain':domain,'entity_id':str(ident),'distance_km':round(d,2),'at':datetime.now(timezone.utc).isoformat(),'confidence':min(s.get('_provenance',{}).get('confidence',1.0),obj.get('_provenance',{}).get('confidence',1.0))})
    return out

def entity_resolution(state:dict):
    entities=[]
    for domain,items in [('satellite',state.get('satellites',{})),('aircraft',state.get('aircraft',{})),('vessel',state.get('vessels',{}))]:
        for ident,obj in items.items():
            entities.append({'entity_id':f'{domain}:{ident}','domain':domain,'identity':str(ident),'observation':obj,'provenance':obj.get('_provenance',{})})
    return entities
