from __future__ import annotations
import asyncio, json, os, sqlite3
from datetime import datetime, timezone, timedelta

DATA_DIR=os.path.join(os.path.dirname(__file__),'..','data'); os.makedirs(DATA_DIR,exist_ok=True)
DB_PATH=os.path.join(DATA_DIR,'quasar.db')
DATABASE_URL=os.getenv('DATABASE_URL','').strip()

SQLITE_SCHEMA='''
CREATE TABLE IF NOT EXISTS satellite_positions (id INTEGER PRIMARY KEY AUTOINCREMENT, recorded_at TEXT NOT NULL, name TEXT NOT NULL, azimuth_deg REAL, elevation_deg REAL, range_km REAL, range_rate_mps REAL, subpoint_lat REAL, subpoint_lon REAL, subpoint_alt_km REAL, above_horizon INTEGER, sunlit INTEGER, station_id TEXT DEFAULT 'default', source TEXT DEFAULT 'ARGUS', confidence REAL DEFAULT 1.0, evidence_json TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS aircraft_observations (id INTEGER PRIMARY KEY AUTOINCREMENT, recorded_at TEXT NOT NULL, icao TEXT, callsign TEXT, lat REAL, lon REAL, altitude_ft REAL, ground_speed_kt REAL, track_deg REAL, squawk TEXT, station_id TEXT DEFAULT 'default', source TEXT DEFAULT 'ARGUS', confidence REAL DEFAULT 1.0, evidence_json TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS vessel_observations (id INTEGER PRIMARY KEY AUTOINCREMENT, recorded_at TEXT NOT NULL, mmsi TEXT, name TEXT, callsign TEXT, lat REAL, lon REAL, sog_kt REAL, cog_deg REAL, heading_deg REAL, station_id TEXT DEFAULT 'default', source TEXT DEFAULT 'ARGUS', confidence REAL DEFAULT 1.0, evidence_json TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS anomalies (id INTEGER PRIMARY KEY AUTOINCREMENT, detected_at TEXT NOT NULL, category TEXT NOT NULL, severity TEXT NOT NULL, subject TEXT, description TEXT, data_json TEXT, fingerprint TEXT, risk_score REAL DEFAULT 0, status TEXT DEFAULT 'NEW', acknowledged INTEGER DEFAULT 0, assignee TEXT, source_count INTEGER DEFAULT 1);
CREATE UNIQUE INDEX IF NOT EXISTS idx_anomaly_fingerprint_time ON anomalies(fingerprint, detected_at);
CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY AUTOINCREMENT, anomaly_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, title TEXT NOT NULL, severity TEXT NOT NULL, risk_score REAL DEFAULT 0, status TEXT DEFAULT 'NEW', assignee TEXT, notes TEXT DEFAULT '', FOREIGN KEY(anomaly_id) REFERENCES anomalies(id));
CREATE TABLE IF NOT EXISTS incident_timeline (id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id INTEGER NOT NULL, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, note TEXT, FOREIGN KEY(incident_id) REFERENCES incidents(id));
CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, generated_at TEXT NOT NULL, period_hours INTEGER, title TEXT, body TEXT, stats_json TEXT DEFAULT '{}', sha256 TEXT);
CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, target TEXT NOT NULL, action TEXT NOT NULL, params_json TEXT, status TEXT DEFAULT 'QUEUED', result_json TEXT, executed_at TEXT, retries INTEGER DEFAULT 0, priority INTEGER DEFAULT 50, requested_by TEXT, station_id TEXT, expires_at TEXT);
CREATE TABLE IF NOT EXISTS correlations (id INTEGER PRIMARY KEY AUTOINCREMENT, detected_at TEXT NOT NULL, type TEXT NOT NULL, entity_a TEXT, entity_b TEXT, confidence REAL DEFAULT 1.0, data_json TEXT);
CREATE TABLE IF NOT EXISTS geofences (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, definition_json TEXT NOT NULL, enabled INTEGER DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS watchlists (id INTEGER PRIMARY KEY AUTOINCREMENT, domain TEXT NOT NULL, value TEXT NOT NULL, label TEXT, priority INTEGER DEFAULT 50, enabled INTEGER DEFAULT 1, created_at TEXT NOT NULL, UNIQUE(domain,value));
CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT, data_json TEXT);
CREATE TABLE IF NOT EXISTS raw_events (id INTEGER PRIMARY KEY AUTOINCREMENT, received_at TEXT NOT NULL, source TEXT NOT NULL, station_id TEXT, event_type TEXT NOT NULL, entity_id TEXT, payload_json TEXT NOT NULL, confidence REAL DEFAULT 1.0, sha256 TEXT);
CREATE TABLE IF NOT EXISTS config_versions (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, actor TEXT NOT NULL, config_json TEXT NOT NULL, sha256 TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sat_time ON satellite_positions(recorded_at); CREATE INDEX IF NOT EXISTS idx_air_time ON aircraft_observations(recorded_at); CREATE INDEX IF NOT EXISTS idx_vessel_time ON vessel_observations(recorded_at); CREATE INDEX IF NOT EXISTS idx_anomaly_status ON anomalies(status,detected_at); CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status,created_at); CREATE INDEX IF NOT EXISTS idx_raw_time ON raw_events(received_at);
'''

PG_SCHEMA='''
CREATE TABLE IF NOT EXISTS satellite_positions (id BIGSERIAL PRIMARY KEY, recorded_at TIMESTAMPTZ NOT NULL, name TEXT NOT NULL, azimuth_deg DOUBLE PRECISION, elevation_deg DOUBLE PRECISION, range_km DOUBLE PRECISION, range_rate_mps DOUBLE PRECISION, subpoint_lat DOUBLE PRECISION, subpoint_lon DOUBLE PRECISION, subpoint_alt_km DOUBLE PRECISION, above_horizon BOOLEAN, sunlit BOOLEAN, station_id TEXT DEFAULT 'default', source TEXT DEFAULT 'ARGUS', confidence DOUBLE PRECISION DEFAULT 1.0, evidence_json JSONB DEFAULT '{}'::jsonb);
CREATE TABLE IF NOT EXISTS aircraft_observations (id BIGSERIAL PRIMARY KEY, recorded_at TIMESTAMPTZ NOT NULL, icao TEXT, callsign TEXT, lat DOUBLE PRECISION, lon DOUBLE PRECISION, altitude_ft DOUBLE PRECISION, ground_speed_kt DOUBLE PRECISION, track_deg DOUBLE PRECISION, squawk TEXT, station_id TEXT DEFAULT 'default', source TEXT DEFAULT 'ARGUS', confidence DOUBLE PRECISION DEFAULT 1.0, evidence_json JSONB DEFAULT '{}'::jsonb);
CREATE TABLE IF NOT EXISTS vessel_observations (id BIGSERIAL PRIMARY KEY, recorded_at TIMESTAMPTZ NOT NULL, mmsi TEXT, name TEXT, callsign TEXT, lat DOUBLE PRECISION, lon DOUBLE PRECISION, sog_kt DOUBLE PRECISION, cog_deg DOUBLE PRECISION, heading_deg DOUBLE PRECISION, station_id TEXT DEFAULT 'default', source TEXT DEFAULT 'ARGUS', confidence DOUBLE PRECISION DEFAULT 1.0, evidence_json JSONB DEFAULT '{}'::jsonb);
CREATE TABLE IF NOT EXISTS anomalies (id BIGSERIAL PRIMARY KEY, detected_at TIMESTAMPTZ NOT NULL, category TEXT NOT NULL, severity TEXT NOT NULL, subject TEXT, description TEXT, data_json JSONB, fingerprint TEXT, risk_score DOUBLE PRECISION DEFAULT 0, status TEXT DEFAULT 'NEW', acknowledged BOOLEAN DEFAULT FALSE, assignee TEXT, source_count INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS incidents (id BIGSERIAL PRIMARY KEY, anomaly_id BIGINT, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, title TEXT NOT NULL, severity TEXT NOT NULL, risk_score DOUBLE PRECISION DEFAULT 0, status TEXT DEFAULT 'NEW', assignee TEXT, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS incident_timeline (id BIGSERIAL PRIMARY KEY, incident_id BIGINT NOT NULL, at TIMESTAMPTZ NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS reports (id BIGSERIAL PRIMARY KEY, generated_at TIMESTAMPTZ NOT NULL, period_hours INTEGER, title TEXT, body TEXT, stats_json JSONB DEFAULT '{}'::jsonb, sha256 TEXT);
CREATE TABLE IF NOT EXISTS tasks (id BIGSERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, target TEXT NOT NULL, action TEXT NOT NULL, params_json JSONB, status TEXT DEFAULT 'QUEUED', result_json JSONB, executed_at TIMESTAMPTZ, retries INTEGER DEFAULT 0, priority INTEGER DEFAULT 50, requested_by TEXT, station_id TEXT, expires_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS correlations (id BIGSERIAL PRIMARY KEY, detected_at TIMESTAMPTZ NOT NULL, type TEXT NOT NULL, entity_a TEXT, entity_b TEXT, confidence DOUBLE PRECISION DEFAULT 1.0, data_json JSONB);
CREATE TABLE IF NOT EXISTS geofences (id BIGSERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, definition_json JSONB NOT NULL, enabled BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS watchlists (id BIGSERIAL PRIMARY KEY, domain TEXT NOT NULL, value TEXT NOT NULL, label TEXT, priority INTEGER DEFAULT 50, enabled BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL, UNIQUE(domain,value));
CREATE TABLE IF NOT EXISTS audit_log (id BIGSERIAL PRIMARY KEY, at TIMESTAMPTZ NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT, data_json JSONB);
CREATE TABLE IF NOT EXISTS raw_events (id BIGSERIAL PRIMARY KEY, received_at TIMESTAMPTZ NOT NULL, source TEXT NOT NULL, station_id TEXT, event_type TEXT NOT NULL, entity_id TEXT, payload_json JSONB NOT NULL, confidence DOUBLE PRECISION DEFAULT 1.0, sha256 TEXT);
CREATE TABLE IF NOT EXISTS config_versions (id BIGSERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL, actor TEXT NOT NULL, config_json JSONB NOT NULL, sha256 TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sat_time ON satellite_positions(recorded_at); CREATE INDEX IF NOT EXISTS idx_air_time ON aircraft_observations(recorded_at); CREATE INDEX IF NOT EXISTS idx_vessel_time ON vessel_observations(recorded_at); CREATE INDEX IF NOT EXISTS idx_anomaly_status ON anomalies(status,detected_at); CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status,created_at); CREATE INDEX IF NOT EXISTS idx_raw_time ON raw_events(received_at);
'''

def _now(): return datetime.now(timezone.utc).isoformat()
def _pg(): return DATABASE_URL.startswith('postgres://') or DATABASE_URL.startswith('postgresql://')
def _adapt(sql): return sql.replace('?', '%s') if _pg() else sql

async def init_db():
    if _pg():
        def run():
            import psycopg
            with psycopg.connect(DATABASE_URL) as c:
                for stmt in [x.strip() for x in PG_SCHEMA.split(';') if x.strip()]: c.execute(stmt)
        await asyncio.to_thread(run)
    else:
        def run():
            with sqlite3.connect(DB_PATH) as db: db.executescript(SQLITE_SCHEMA); db.commit()
        await asyncio.to_thread(run)

async def query(sql,params=()):
    if _pg():
        def run():
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(DATABASE_URL,row_factory=dict_row) as c: return list(c.execute(_adapt(sql),params).fetchall())
        return await asyncio.to_thread(run)
    def run():
        with sqlite3.connect(DB_PATH) as db:
            db.row_factory=sqlite3.Row
            return [dict(r) for r in db.execute(sql,params).fetchall()]
    return await asyncio.to_thread(run)

async def execute(sql,params=(),returning=False):
    if _pg():
        def run():
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(DATABASE_URL,row_factory=dict_row) as c:
                cur=c.execute(_adapt(sql),params)
                row=cur.fetchone() if returning else None
                return dict(row) if row else None
        return await asyncio.to_thread(run)
    def run():
        with sqlite3.connect(DB_PATH) as db:
            cur=db.execute(sql,params); db.commit()
            return {'id':cur.lastrowid} if returning else None
    return await asyncio.to_thread(run)

async def record_raw_event(source,station_id,event_type,entity_id,payload,confidence=1.0):
    import hashlib
    raw=json.dumps(payload,sort_keys=True,default=str,separators=(',',':')); sha=hashlib.sha256(raw.encode()).hexdigest()
    await execute('INSERT INTO raw_events(received_at,source,station_id,event_type,entity_id,payload_json,confidence,sha256) VALUES(?,?,?,?,?,?,?,?)',(_now(),source,station_id,event_type,entity_id,raw if not _pg() else json.dumps(payload),confidence,sha))

async def record_satellite(pos,station_id='default'):
    prov=pos.get('_provenance',{}); await record_raw_event(prov.get('source','ARGUS'),station_id,'satellite',pos.get('name'),pos,prov.get('confidence',1.0))
    await execute('INSERT INTO satellite_positions(recorded_at,name,azimuth_deg,elevation_deg,range_km,range_rate_mps,subpoint_lat,subpoint_lon,subpoint_alt_km,above_horizon,sunlit,station_id,source,confidence,evidence_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(_now(),pos.get('name'),pos.get('azimuth_deg'),pos.get('elevation_deg'),pos.get('range_km'),pos.get('range_rate_mps'),pos.get('subpoint_lat'),pos.get('subpoint_lon'),pos.get('subpoint_alt_km'),bool(pos.get('above_horizon')),pos.get('sunlit'),station_id,prov.get('source','ARGUS'),prov.get('confidence',1.0),json.dumps(prov)))

async def record_aircraft(items,station_id='default'):
    for a in items:
        prov=a.get('_provenance',{}); await record_raw_event(prov.get('source','ARGUS'),station_id,'aircraft',a.get('icao'),a,prov.get('confidence',1.0))
        await execute('INSERT INTO aircraft_observations(recorded_at,icao,callsign,lat,lon,altitude_ft,ground_speed_kt,track_deg,squawk,station_id,source,confidence,evidence_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(_now(),a.get('icao'),a.get('callsign'),a.get('lat'),a.get('lon'),a.get('altitude_ft'),a.get('ground_speed_kt'),a.get('track_deg'),a.get('squawk'),station_id,prov.get('source','ARGUS'),prov.get('confidence',1.0),json.dumps(prov)))

async def record_vessels(items,station_id='default'):
    for v in items:
        prov=v.get('_provenance',{}); await record_raw_event(prov.get('source','ARGUS'),station_id,'vessel',str(v.get('mmsi')),v,prov.get('confidence',1.0))
        await execute('INSERT INTO vessel_observations(recorded_at,mmsi,name,callsign,lat,lon,sog_kt,cog_deg,heading_deg,station_id,source,confidence,evidence_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(_now(),str(v.get('mmsi')),v.get('name'),v.get('callsign'),v.get('lat'),v.get('lon'),v.get('sog_kt'),v.get('cog_deg'),v.get('heading_deg'),station_id,prov.get('source','ARGUS'),prov.get('confidence',1.0),json.dumps(prov)))

async def record_anomaly(category,severity,subject,description,data=None,fingerprint=None,risk_score=0,source_count=1):
    row=await execute('INSERT INTO anomalies(detected_at,category,severity,subject,description,data_json,fingerprint,risk_score,source_count) VALUES(?,?,?,?,?,?,?,?,?)'+(' RETURNING id' if _pg() else ''),(_now(),category,severity,subject,description,json.dumps(data or {}),fingerprint,risk_score,source_count),returning=True)
    return row['id'] if row else None

async def save_report(title,body,period_hours,stats=None,sha256=None):
    await execute('INSERT INTO reports(generated_at,period_hours,title,body,stats_json,sha256) VALUES(?,?,?,?,?,?)',(_now(),period_hours,title,body,json.dumps(stats or {}),sha256))

async def create_incident(anomaly_id,title,severity,risk_score,assignee=None):
    now=_now(); row=await execute('INSERT INTO incidents(anomaly_id,created_at,updated_at,title,severity,risk_score,status,assignee) VALUES(?,?,?,?,?,?,?,?)'+(' RETURNING id' if _pg() else ''),(anomaly_id,now,now,title,severity,risk_score,'NEW',assignee),returning=True)
    iid=row['id']; await execute('INSERT INTO incident_timeline(incident_id,at,actor,action,note) VALUES(?,?,?,?,?)',(iid,now,'system','CREATED','Created from anomaly')); return iid

async def update_incident_status(iid,status,actor,note=''):
    await execute('UPDATE incidents SET status=?,updated_at=?,notes=? WHERE id=?',(status,_now(),note,iid)); await execute('INSERT INTO incident_timeline(incident_id,at,actor,action,note) VALUES(?,?,?,?,?)',(iid,_now(),actor,status,note)); return True

async def acknowledge_anomaly(anomaly_id,actor='unknown'):
    await execute("UPDATE anomalies SET acknowledged=?,status='ACKNOWLEDGED' WHERE id=?",(True,anomaly_id)); await audit(actor,'ACKNOWLEDGE_ANOMALY',str(anomaly_id),{})

async def create_task(target,action,params,requested_by='system',station_id=None,priority=50,expires_at=None):
    now=_now(); row=await execute('INSERT INTO tasks(created_at,updated_at,target,action,params_json,status,priority,requested_by,station_id,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?)'+(' RETURNING id' if _pg() else ''),(now,now,target,action,json.dumps(params or {}),'QUEUED',priority,requested_by,station_id,expires_at),returning=True); return row['id']

async def update_task(task_id,status,result=None,retry_delta=0):
    rows=await query('SELECT retries FROM tasks WHERE id=?',(task_id,)); retries=(rows[0]['retries'] if rows else 0)+retry_delta
    await execute('UPDATE tasks SET status=?,result_json=?,updated_at=?,executed_at=?,retries=? WHERE id=?',(status,json.dumps(result or {}),_now(),_now() if status in ('COMPLETED','FAILED') else None,retries,task_id))

async def record_correlation(c):
    await execute('INSERT INTO correlations(detected_at,type,entity_a,entity_b,confidence,data_json) VALUES(?,?,?,?,?,?)',(_now(),c.get('type'),str(c.get('satellite') or c.get('entity_a') or ''),str(c.get('entity_id') or c.get('entity_b') or ''),c.get('confidence',1.0),json.dumps(c)))

async def audit(actor,action,target='',data=None): await execute('INSERT INTO audit_log(at,actor,action,target,data_json) VALUES(?,?,?,?,?)',(_now(),actor,action,target,json.dumps(data or {})))

async def purge_old_observations(days=30):
    cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
    for table in ('satellite_positions','aircraft_observations','vessel_observations','raw_events'): await execute(f'DELETE FROM {table} WHERE '+('received_at' if table=='raw_events' else 'recorded_at')+' < ?',(cutoff,))

async def save_config_version(actor,config):
    import hashlib
    raw=json.dumps(config,sort_keys=True,default=str); sha=hashlib.sha256(raw.encode()).hexdigest(); await execute('INSERT INTO config_versions(created_at,actor,config_json,sha256) VALUES(?,?,?,?)',(_now(),actor,raw,sha)); return sha
