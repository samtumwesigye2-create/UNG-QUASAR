from __future__ import annotations
import hashlib, json
from . import history

async def incident_bundle(incident_id:int):
    incidents=await history.query('SELECT * FROM incidents WHERE id=?',(incident_id,))
    if not incidents: return None
    inc=incidents[0]
    timeline=await history.query('SELECT * FROM incident_timeline WHERE incident_id=? ORDER BY at ASC',(incident_id,))
    anomaly=[]
    if inc.get('anomaly_id'): anomaly=await history.query('SELECT * FROM anomalies WHERE id=?',(inc['anomaly_id'],))
    bundle={'incident':inc,'anomaly':anomaly[0] if anomaly else None,'timeline':timeline}
    canonical=json.dumps(bundle,sort_keys=True,default=str,separators=(',',':')).encode()
    bundle['sha256']=hashlib.sha256(canonical).hexdigest()
    return bundle
