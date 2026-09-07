from __future__ import annotations
from datetime import datetime, timezone
_vessel_last_seen={}; _vessel_last_pos={}; _aircraft_squawks={}; _sat_sunlit={}

def check_vessel_dark(vessels,dark_threshold_minutes=15):
    now=datetime.now(timezone.utc); out=[]
    for mmsi,v in vessels.items():
        recv=v.get('received_at') or v.get('_provenance',{}).get('received_at')
        if not recv: continue
        try: mins=(now-datetime.fromisoformat(recv.replace('Z','+00:00'))).total_seconds()/60
        except Exception: continue
        was=mmsi in _vessel_last_seen; _vessel_last_seen[mmsi]=recv
        if was and mins>dark_threshold_minutes:
            name=v.get('name') or f'MMSI {mmsi}'; out.append(('vessel_dark','WARNING',name,f'{name} has not transmitted AIS in {int(mins)} minutes.',{'mmsi':mmsi,'minutes_silent':round(mins,1),'last_position':_vessel_last_pos.get(mmsi)}))
        if v.get('lat') is not None and v.get('lon') is not None: _vessel_last_pos[mmsi]=(v['lat'],v['lon'])
    return out

def check_squawk_7700(aircraft):
    out=[]; codes={'7700':'EMERGENCY (7700)','7600':'Radio failure (7600)','7500':'Hijack (7500)'}
    for icao,a in aircraft.items():
        sq=str(a.get('squawk') or ''); prev=_aircraft_squawks.get(icao); _aircraft_squawks[icao]=sq
        if sq in codes and prev!=sq:
            cs=a.get('callsign') or icao; out.append(('emergency_squawk','CRITICAL',cs,f'{cs} is squawking {codes[sq]}',{'icao':icao,'squawk':sq,'lat':a.get('lat'),'lon':a.get('lon')}))
    return out

def check_satellite_eclipse(sats):
    out=[]
    for name,p in sats.items():
        sun=p.get('sunlit'); prev=_sat_sunlit.get(name); _sat_sunlit[name]=sun
        if sun is False and prev is not False: out.append(('satellite_eclipse','INFO',name,f"{name} entered Earth's shadow.",{'name':name,'subpoint_lat':p.get('subpoint_lat'),'subpoint_lon':p.get('subpoint_lon')}))
    return out

def check_debris_overhead(sats,threshold=20.0):
    out=[]
    for name,p in sats.items():
        if any(k in name.upper() for k in ['DEB','R/B','DEBRIS','ROCKET']) and float(p.get('elevation_deg') or -90)>=threshold:
            out.append(('debris_overhead','WARNING',name,f'Debris object {name} is {round(float(p.get("elevation_deg")),1)}° above horizon.',{'name':name,'elevation_deg':p.get('elevation_deg'),'azimuth_deg':p.get('azimuth_deg'),'range_km':p.get('range_km')}))
    return out

def check_stale_tracks(state):
    out=[]
    for domain in ('aircraft','vessels','satellites'):
        for ident,obj in state.get(domain,{}).items():
            if obj.get('_stale'): out.append(('lost_track','WARNING',str(ident),f'{domain[:-1].title()} {ident} track is stale/lost.',{'domain':domain,'entity_id':str(ident)}))
    return out

def run_all_checks(state,dark_threshold_minutes=15,debris_threshold=20.0):
    out=[]; out+=check_vessel_dark(state.get('vessels',{}),dark_threshold_minutes); out+=check_squawk_7700(state.get('aircraft',{})); out+=check_satellite_eclipse(state.get('satellites',{})); out+=check_debris_overhead(state.get('satellites',{}),debris_threshold); out+=check_stale_tracks(state); return out
