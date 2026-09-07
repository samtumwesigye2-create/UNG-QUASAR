from __future__ import annotations
from datetime import datetime, timezone, timedelta
import hashlib, json
from . import history, health

async def generate_report(period_hours=24):
    now=datetime.now(timezone.utc); cutoff=(now-timedelta(hours=period_hours)).isoformat()
    sats=await history.query('SELECT name, COUNT(*) as obs, MAX(elevation_deg) as max_el FROM satellite_positions WHERE recorded_at>? AND above_horizon=? GROUP BY name ORDER BY obs DESC',(cutoff,True))
    air=await history.query('SELECT COUNT(DISTINCT icao) as unique_aircraft, COUNT(*) as total_obs FROM aircraft_observations WHERE recorded_at>?',(cutoff,))
    vessels=await history.query('SELECT COUNT(DISTINCT mmsi) as unique_vessels, COUNT(*) as total_obs FROM vessel_observations WHERE recorded_at>?',(cutoff,))
    anomalies=await history.query('SELECT category,severity,subject,description,detected_at,risk_score,status FROM anomalies WHERE detected_at>? ORDER BY risk_score DESC,detected_at DESC',(cutoff,))
    incidents=await history.query('SELECT status,COUNT(*) as n FROM incidents WHERE created_at>? GROUP BY status',(cutoff,))
    tasks=await history.query('SELECT status,COUNT(*) as n FROM tasks WHERE created_at>? GROUP BY status',(cutoff,))
    lines=['QUASAR Intelligence Report',f'Period: Last {period_hours} hours',f'Generated: {now.strftime("%Y-%m-%d %H:%M:%S UTC")}','='*64,'','SATELLITE TRACKING']
    lines += [f"  - {r['name']}: {r['obs']} observations, max elevation {round(float(r['max_el'] or 0),1)}°" for r in sats] or ['  No satellite passes recorded.']
    lines += ['', 'AIRCRAFT (ADS-B)', f"  {air[0]['unique_aircraft'] or 0} unique aircraft ({air[0]['total_obs'] or 0} observations)" if air else '  No aircraft data.']
    lines += ['', 'VESSELS (AIS)', f"  {vessels[0]['unique_vessels'] or 0} unique vessels ({vessels[0]['total_obs'] or 0} observations)" if vessels else '  No vessel data.']
    lines += ['', 'ANOMALIES & INCIDENTS']
    if anomalies:
        for a in anomalies[:20]: lines.append(f"  [{a['severity']}] risk={a['risk_score']} {a['subject']} — {a['description']} ({a['status']})")
    else: lines.append('  No anomalies detected.')
    lines += ['', 'WORKFLOW', '  Incidents: '+', '.join(f"{x['status']}={x['n']}" for x in incidents) if incidents else '  Incidents: none', '  Tasks: '+', '.join(f"{x['status']}={x['n']}" for x in tasks) if tasks else '  Tasks: none', '', '='*64]
    body='\n'.join(lines); stats={'satellites_tracked':len(sats),'unique_aircraft':air[0]['unique_aircraft'] if air else 0,'unique_vessels':vessels[0]['unique_vessels'] if vessels else 0,'anomalies':len(anomalies)}; sha=hashlib.sha256(body.encode()).hexdigest(); title=f"QUASAR {period_hours}h Report — {now.strftime('%Y-%m-%d %H:%M UTC')}"; await history.save_report(title,body,period_hours,stats,sha); health.mark_report(); return {'title':title,'body':body,'stats':stats,'sha256':sha}
