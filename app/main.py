from __future__ import annotations
import asyncio, json, os
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException, Body, Depends, Query
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import QuasarConfig, load_config, save_config
from .security import current_principal, require_role, Principal
from . import history, fusion, patterns, reports, tasking, health, correlation, incidents, rules, replay, geofences, notifications, evidence, scheduling

APP_VERSION='2.0.0'
STATIC_DIR=os.path.join(os.path.dirname(__file__),'..','static')

async def _emit_anomaly(category,severity,subject,description,data,cfg:QuasarConfig):
    ok,fp=rules.should_emit(category,subject,data,cfg.anomaly_cooldown_s)
    if not ok: return None
    conf=float((data or {}).get('confidence',1.0))
    risk=correlation.risk_score(severity,conf,(data or {}).get('source_count',1),(data or {}).get('minutes_to_event'),(data or {}).get('persistence',1))
    aid=await history.record_anomaly(category,severity,subject,description,data,fp,risk,(data or {}).get('source_count',1))
    if severity in ('WARNING','CRITICAL') and aid:
        await incidents.create_from_anomaly(aid,f'{category}: {subject}',severity,risk)
    if severity in cfg.notify_severities:
        await asyncio.to_thread(notifications.send_alert,{'system':'UNG-QUASAR','category':category,'severity':severity,'subject':subject,'description':description,'risk_score':risk,'data':data})
    return aid

async def _watchlist_checks(state,cfg):
    rows=await history.query('SELECT * FROM watchlists WHERE enabled=?',(True,))
    for w in rows:
        domain=str(w['domain']).lower(); value=str(w['value']).lower(); hit=None
        bucket={'aircraft':'aircraft','vessel':'vessels','satellite':'satellites'}.get(domain)
        if not bucket: continue
        for ident,obj in state.get(bucket,{}).items():
            candidates=[str(ident).lower(),str(obj.get('callsign') or '').lower(),str(obj.get('name') or '').lower()]
            if value in candidates: hit=(ident,obj); break
        if hit:
            await _emit_anomaly('watchlist_match','WARNING',str(hit[0]),f'{domain.title()} {hit[0]} matched watchlist {w.get("label") or w["value"]}.',{'domain':domain,'watchlist_id':w['id'],'priority':w.get('priority',50)},cfg)

async def _geofence_checks(state,cfg):
    rows=await history.query('SELECT * FROM geofences WHERE enabled=?',(True,))
    defs=[]
    for r in rows:
        try:
            d=json.loads(r['definition_json']) if isinstance(r['definition_json'],str) else r['definition_json']; d['name']=r['name']; defs.append(d)
        except Exception: pass
    for hit in geofences.evaluate(state,defs):
        await _emit_anomaly('geofence_intersection','INFO',hit['entity_id'],f"{hit['domain'].title()} {hit['entity_id']} is inside {hit['fence']}.",hit,cfg)

async def _main_loop():
    while True:
        cfg=load_config()
        try:
            await fusion.collect_cycle(cfg.argus_url,cfg.tracked_satellites,cfg.station_id)
            fusion.mark_stale(cfg.stale_after_s)
            state=fusion.get_state()
            corr=correlation.correlate(state); state['correlations']=corr; state['entities']=correlation.entity_resolution(state)
            for c in corr: await history.record_correlation(c)
            for category,severity,subject,description,data in patterns.run_all_checks(state,cfg.dark_vessel_minutes,cfg.debris_elevation_threshold_deg):
                await _emit_anomaly(category,severity,subject,description,data,cfg)
            await _watchlist_checks(state,cfg); await _geofence_checks(state,cfg); health.mark_patterns()
        except Exception as e:
            health.mark_collection(False,error=str(e))
        await asyncio.sleep(cfg.collection_interval_s)

async def _task_retry_loop():
    while True:
        await asyncio.sleep(20)
        cfg=load_config()
        try:
            rows=await history.query("SELECT * FROM tasks WHERE status IN ('QUEUED','RETRYING') ORDER BY priority DESC,created_at ASC LIMIT 20")
            for row in rows:
                if row.get('expires_at') and row['expires_at'] < datetime.now(timezone.utc).isoformat():
                    await history.update_task(row['id'],'EXPIRED',{'reason':'task expired'}); continue
                if int(row.get('retries') or 0)>=cfg.max_task_retries:
                    await history.update_task(row['id'],'FAILED',{'reason':'retry limit reached'}); continue
                try: params=json.loads(row['params_json']) if isinstance(row['params_json'],str) else (row['params_json'] or {})
                except Exception: params={}
                await history.update_task(row['id'],'EXECUTING',{})
                result=await asyncio.to_thread(tasking.execute,cfg.argus_url,row['action'],params)
                await history.update_task(row['id'],'COMPLETED' if result.get('ok') else 'RETRYING',result,0 if result.get('ok') else 1)
        except Exception: pass

async def _purge_loop():
    while True:
        await asyncio.sleep(86400)
        try: await history.purge_old_observations(load_config().raw_retention_days)
        except Exception: pass

@asynccontextmanager
async def lifespan(app:FastAPI):
    await history.init_db()
    tasks=[asyncio.create_task(_main_loop()),asyncio.create_task(_task_retry_loop()),asyncio.create_task(_purge_loop())]
    yield
    for t in tasks: t.cancel()

app=FastAPI(title='UNG-QUASAR — Quantified Universal Analytics, Signals & Reporting',version=APP_VERSION,lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=load_config().cors_origins,allow_credentials=True,allow_methods=['GET','POST','PUT','PATCH','DELETE'],allow_headers=['Authorization','Content-Type','X-QUASAR-API-Key'])
app.mount('/static',StaticFiles(directory=STATIC_DIR),name='static')

@app.get('/')
def dashboard(): return FileResponse(os.path.join(STATIC_DIR,'index.html'))
@app.get('/health')
@app.get('/v1/health')
def health_endpoint(): return {'status':'ok','service':'ung-quasar','version':APP_VERSION,**health.snapshot()}
@app.get('/ready')
@app.get('/v1/ready')
async def ready():
    try: await history.query('SELECT 1 AS ok'); db=True
    except Exception: db=False
    hs=health.snapshot(); return {'ready':db,'database_ready':db,'argus_reachable':hs.get('argus_reachable',False),'last_collection_ok':hs.get('last_collection_ok')}
@app.get('/v1/metrics')
async def metrics(p:Principal=Depends(require_role('viewer'))):
    counts={}
    for table in ('satellite_positions','aircraft_observations','vessel_observations','anomalies','incidents','tasks','raw_events'):
        r=await history.query(f'SELECT COUNT(*) AS n FROM {table}'); counts[table]=r[0]['n'] if r else 0
    return {'health':health.snapshot(),'counts':counts}

@app.get('/api/config')
@app.get('/v1/config')
def get_config(p:Principal=Depends(require_role('viewer'))): return load_config().model_dump()
@app.post('/api/config')
@app.post('/v1/config')
async def set_config(cfg:QuasarConfig,p:Principal=Depends(require_role('commander'))):
    save_config(cfg); sha=await history.save_config_version(p.subject,cfg.model_dump()); await history.audit(p.subject,'CONFIG_UPDATE','quasar',{'sha256':sha}); return {'ok':True,'config':cfg.model_dump(),'version_sha256':sha}
@app.get('/v1/config/versions')
async def config_versions(limit:int=20,p:Principal=Depends(require_role('commander'))): return {'versions':await history.query('SELECT id,created_at,actor,sha256 FROM config_versions ORDER BY created_at DESC LIMIT ?',(limit,))}

@app.get('/api/picture')
@app.get('/v1/picture')
def current_picture(p:Principal=Depends(require_role('viewer'))):
    s=fusion.get_state(); return {'last_updated':s.get('last_updated'),'satellites':list(s['satellites'].values()),'aircraft':list(s['aircraft'].values()),'vessels':list(s['vessels'].values()),'entities':s.get('entities',[]),'correlations':s.get('correlations',[]),'satellite_count':len(s['satellites']),'aircraft_count':len(s['aircraft']),'vessel_count':len(s['vessels']),'counts':{'satellites':len(s['satellites']),'aircraft':len(s['aircraft']),'vessels':len(s['vessels'])}}
@app.get('/v1/timeline')
async def timeline(hours:int=24,limit:int=500,p:Principal=Depends(require_role('analyst'))):
    cutoff=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat()
    anomalies=await history.query('SELECT detected_at AS at,category AS type,subject,severity,description FROM anomalies WHERE detected_at>? ORDER BY detected_at DESC LIMIT ?',(cutoff,limit))
    tasks=await history.query('SELECT created_at AS at,action AS type,target AS subject,status AS severity,result_json AS description FROM tasks WHERE created_at>? ORDER BY created_at DESC LIMIT ?',(cutoff,limit))
    corr=await history.query('SELECT detected_at AS at,type,entity_a AS subject,confidence AS severity,data_json AS description FROM correlations WHERE detected_at>? ORDER BY detected_at DESC LIMIT ?',(cutoff,limit))
    return {'events':sorted(anomalies+tasks+corr,key=lambda x:x['at'],reverse=True)[:limit]}

@app.get('/api/history/satellites')
async def satellite_history(name:str='',hours:int=24,limit:int=500,p:Principal=Depends(require_role('viewer'))):
    cutoff=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat(); sql='SELECT * FROM satellite_positions WHERE recorded_at>?'; params=[cutoff]
    if name: sql+=' AND name LIKE ?'; params.append(f'%{name}%')
    sql+=' ORDER BY recorded_at DESC LIMIT ?'; params.append(limit); rows=await history.query(sql,tuple(params)); return {'rows':rows,'count':len(rows)}
@app.get('/api/history/aircraft')
async def aircraft_history(icao:str='',callsign:str='',hours:int=24,limit:int=500,p:Principal=Depends(require_role('viewer'))):
    cutoff=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat(); sql='SELECT * FROM aircraft_observations WHERE recorded_at>?'; params=[cutoff]
    if icao: sql+=' AND icao=?'; params.append(icao)
    elif callsign: sql+=' AND callsign LIKE ?'; params.append(f'%{callsign}%')
    sql+=' ORDER BY recorded_at DESC LIMIT ?'; params.append(limit); rows=await history.query(sql,tuple(params)); return {'rows':rows,'count':len(rows)}
@app.get('/api/history/vessels')
async def vessel_history(mmsi:str='',hours:int=24,limit:int=500,p:Principal=Depends(require_role('viewer'))):
    cutoff=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat(); sql='SELECT * FROM vessel_observations WHERE recorded_at>?'; params=[cutoff]
    if mmsi: sql+=' AND mmsi=?'; params.append(mmsi)
    sql+=' ORDER BY recorded_at DESC LIMIT ?'; params.append(limit); rows=await history.query(sql,tuple(params)); return {'rows':rows,'count':len(rows)}
@app.get('/api/history/stats')
async def history_stats(p:Principal=Depends(require_role('viewer'))):
    sat=await history.query('SELECT COUNT(*) AS n, MIN(recorded_at) AS oldest FROM satellite_positions')
    air=await history.query('SELECT COUNT(DISTINCT icao) AS n FROM aircraft_observations')
    ves=await history.query('SELECT COUNT(DISTINCT mmsi) AS n FROM vessel_observations')
    an=await history.query('SELECT COUNT(*) AS n FROM anomalies')
    return {'total_satellite_observations':sat[0]['n'] if sat else 0,'unique_aircraft_seen':air[0]['n'] if air else 0,'unique_vessels_seen':ves[0]['n'] if ves else 0,'total_anomalies':an[0]['n'] if an else 0,'oldest_record':sat[0]['oldest'] if sat else None}

@app.get('/api/anomalies')
@app.get('/v1/anomalies')
async def get_anomalies(status:str='NEW',limit:int=100,p:Principal=Depends(require_role('viewer'))): return {'anomalies':await history.query('SELECT * FROM anomalies WHERE status=? ORDER BY risk_score DESC,detected_at DESC LIMIT ?',(status.upper(),limit))}
@app.post('/api/anomalies/{anomaly_id}/acknowledge')
async def acknowledge(anomaly_id:int,p:Principal=Depends(require_role('analyst'))): await history.acknowledge_anomaly(anomaly_id,p.subject); return {'ok':True}

@app.get('/v1/incidents')
async def list_incidents(status:str|None=None,limit:int=100,p:Principal=Depends(require_role('viewer'))):
    return {'incidents':await history.query(('SELECT * FROM incidents WHERE status=? ORDER BY risk_score DESC,updated_at DESC LIMIT ?' if status else 'SELECT * FROM incidents ORDER BY risk_score DESC,updated_at DESC LIMIT ?'),((status.upper(),limit) if status else (limit,)))}
@app.post('/v1/incidents/{incident_id}/transition')
async def transition_incident(incident_id:int,status:str=Body(embed=True),note:str=Body(default='',embed=True),p:Principal=Depends(require_role('analyst'))):
    try: await incidents.transition(incident_id,status,p.subject,note)
    except ValueError as e: raise HTTPException(400,str(e))
    return {'ok':True,'incident_id':incident_id,'status':status.upper()}
@app.get('/v1/incidents/{incident_id}/evidence')
async def incident_evidence(incident_id:int,p:Principal=Depends(require_role('analyst'))):
    bundle=await evidence.incident_bundle(incident_id)
    if not bundle: raise HTTPException(404,'Incident not found')
    return bundle

@app.post('/api/reports/generate')
@app.post('/v1/reports/generate')
async def generate_report(period_hours:int=24,p:Principal=Depends(require_role('analyst'))): return await reports.generate_report(period_hours)
@app.get('/api/reports/generate',response_class=PlainTextResponse)
async def generate_report_text(period_hours:int=24,p:Principal=Depends(require_role('analyst'))): return (await reports.generate_report(period_hours))['body']
@app.get('/api/reports')
@app.get('/v1/reports')
async def list_reports(limit:int=20,p:Principal=Depends(require_role('viewer'))): return {'reports':await history.query('SELECT id,generated_at,period_hours,title,sha256 FROM reports ORDER BY generated_at DESC LIMIT ?',(limit,))}
@app.get('/api/reports/{report_id}')
async def get_report(report_id:int,p:Principal=Depends(require_role('viewer'))):
    rows=await history.query('SELECT * FROM reports WHERE id=?',(report_id,));
    if not rows: raise HTTPException(404,'Report not found')
    return rows[0]

async def _queue_task(action,params,p,priority=50):
    tid=await history.create_task('ARGUS',action,params,p.subject,params.get('station_id'),priority)
    await history.audit(p.subject,'TASK_CREATE',str(tid),{'action':action,'params':params}); return {'queued':True,'task_id':tid,'status':'QUEUED'}
@app.post('/api/task/track')
async def task_track(name:str,group:str='active',station_id:str='default',priority:int=50,p:Principal=Depends(require_role('operator'))): return await _queue_task('track_satellite',{'name':name,'group':group,'station_id':station_id},p,priority)
@app.post('/api/task/watch')
async def task_watch(name:str,group:str='active',station_id:str='default',priority:int=50,p:Principal=Depends(require_role('operator'))): return await _queue_task('watch_alerts',{'name':name,'group':group,'station_id':station_id},p,priority)
@app.get('/api/task/passes')
def task_passes(name:str,hours:int=24,station_id:str='default',p:Principal=Depends(require_role('viewer'))):
    r=tasking.task_get_passes(load_config().argus_url,name,hours,station_id)
    if not r['ok']: raise HTTPException(503,r['error'])
    return r['data']
@app.get('/api/task/conjunctions')
def task_conjunctions(name:str,threshold_km:float=25.0,p:Principal=Depends(require_role('viewer'))):
    r=tasking.task_get_conjunctions(load_config().argus_url,name,threshold_km)
    if not r['ok']: raise HTTPException(503,r['error'])
    return r['data']
@app.get('/v1/tasks')
async def tasks(status:str|None=None,limit:int=100,p:Principal=Depends(require_role('viewer'))):
    return {'tasks':await history.query(('SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC LIMIT ?' if status else 'SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?'),((status.upper(),limit) if status else (limit,)))}

@app.post('/v1/replay')
async def run_replay(hours:int=1,limit:int=5000,p:Principal=Depends(require_role('analyst'))): return await replay.replay(hours,limit)

@app.get('/v1/watchlists')
async def list_watchlists(p:Principal=Depends(require_role('viewer'))): return {'watchlists':await history.query('SELECT * FROM watchlists ORDER BY priority DESC,created_at DESC')}
@app.post('/v1/watchlists')
async def add_watchlist(domain:str,value:str,label:str='',priority:int=50,p:Principal=Depends(require_role('analyst'))):
    await history.execute('INSERT INTO watchlists(domain,value,label,priority,enabled,created_at) VALUES(?,?,?,?,?,?)',(domain.lower(),value,label,priority,True,datetime.now(timezone.utc).isoformat())); await history.audit(p.subject,'WATCHLIST_ADD',f'{domain}:{value}',{}); return {'ok':True}
@app.delete('/v1/watchlists/{watch_id}')
async def delete_watchlist(watch_id:int,p:Principal=Depends(require_role('analyst'))): await history.execute('DELETE FROM watchlists WHERE id=?',(watch_id,)); return {'ok':True}

@app.get('/v1/geofences')
async def list_geofences(p:Principal=Depends(require_role('viewer'))): return {'geofences':await history.query('SELECT * FROM geofences ORDER BY name')}
@app.post('/v1/geofences')
async def add_geofence(name:str,definition:dict=Body(...),p:Principal=Depends(require_role('analyst'))):
    await history.execute('INSERT INTO geofences(name,definition_json,enabled,created_at) VALUES(?,?,?,?)',(name,json.dumps(definition),True,datetime.now(timezone.utc).isoformat())); await history.audit(p.subject,'GEOFENCE_ADD',name,definition); return {'ok':True}
@app.delete('/v1/geofences/{fence_id}')
async def delete_geofence(fence_id:int,p:Principal=Depends(require_role('analyst'))): await history.execute('DELETE FROM geofences WHERE id=?',(fence_id,)); return {'ok':True}

@app.post('/v1/stations/select')
def station_select(stations:list[dict]=Body(...),required_capabilities:list[str]=Query(default=[]),p:Principal=Depends(require_role('operator'))):
    choice=scheduling.select_station(stations,required_capabilities)
    if not choice: raise HTTPException(404,'No eligible station')
    return choice

@app.get('/v1/audit')
async def audit_log(limit:int=200,p:Principal=Depends(require_role('admin'))): return {'events':await history.query('SELECT * FROM audit_log ORDER BY at DESC LIMIT ?',(limit,))}
