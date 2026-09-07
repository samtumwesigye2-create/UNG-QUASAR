from __future__ import annotations
from .correlation import haversine_km

def contains(fence:dict,lat:float,lon:float)->bool:
    if fence.get('type','circle')=='circle':
        d=haversine_km(lat,lon,fence.get('lat'),fence.get('lon'))
        return d is not None and d<=float(fence.get('radius_km',0))
    pts=fence.get('points') or []
    inside=False; j=len(pts)-1
    for i in range(len(pts)):
        yi,xi=float(pts[i][0]),float(pts[i][1]); yj,xj=float(pts[j][0]),float(pts[j][1])
        if ((yi>lat)!=(yj>lat)) and (lon < (xj-xi)*(lat-yi)/((yj-yi) or 1e-12)+xi): inside=not inside
        j=i
    return inside

def evaluate(state:dict,fences:list[dict]):
    hits=[]
    for domain,items in [('aircraft',state.get('aircraft',{})),('vessel',state.get('vessels',{}))]:
        for ident,obj in items.items():
            if obj.get('lat') is None or obj.get('lon') is None: continue
            for f in fences:
                if contains(f,obj['lat'],obj['lon']): hits.append({'fence':f.get('name'),'entity_id':str(ident),'domain':domain,'lat':obj['lat'],'lon':obj['lon']})
    return hits
