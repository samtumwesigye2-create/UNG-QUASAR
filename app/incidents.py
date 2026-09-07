from __future__ import annotations
from . import history

VALID={'NEW','ACKNOWLEDGED','INVESTIGATING','RESOLVED','DISMISSED'}

async def create_from_anomaly(anomaly_id:int, title:str, severity:str, risk_score:float, assignee:str|None=None):
    return await history.create_incident(anomaly_id,title,severity,risk_score,assignee)

async def transition(incident_id:int,status:str,actor:str,note:str=''):
    status=status.upper()
    if status not in VALID: raise ValueError('invalid incident status')
    return await history.update_incident_status(incident_id,status,actor,note)
