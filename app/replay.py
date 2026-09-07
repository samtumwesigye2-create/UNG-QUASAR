from __future__ import annotations
from datetime import datetime, timedelta, timezone
from . import history, patterns, correlation

async def replay(hours:int=1, limit:int=5000):
    cutoff=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat()
    sats=await history.query('SELECT * FROM satellite_positions WHERE recorded_at>=? ORDER BY recorded_at ASC LIMIT ?',(cutoff,limit))
    air=await history.query('SELECT * FROM aircraft_observations WHERE recorded_at>=? ORDER BY recorded_at ASC LIMIT ?',(cutoff,limit))
    vessels=await history.query('SELECT * FROM vessel_observations WHERE recorded_at>=? ORDER BY recorded_at ASC LIMIT ?',(cutoff,limit))
    state={'satellites':{},'aircraft':{},'vessels':{}}
    for r in sats: state['satellites'][r['name']]=r
    for r in air:
        if r.get('icao'): state['aircraft'][r['icao']]=r
    for r in vessels:
        if r.get('mmsi'): state['vessels'][str(r['mmsi'])]=r
    detected=patterns.run_all_checks(state)
    return {'hours':hours,'observations':{'satellites':len(sats),'aircraft':len(air),'vessels':len(vessels)},'detected':[{'category':x[0],'severity':x[1],'subject':x[2],'description':x[3],'data':x[4]} for x in detected],'correlations':correlation.correlate(state)}
