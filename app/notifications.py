from __future__ import annotations
import os, requests
HERMES_BASE_URL=os.getenv('HERMES_BASE_URL','').rstrip('/')
HERMES_API_KEY=os.getenv('HERMES_API_KEY','').strip()

def send_alert(payload:dict)->dict:
    if not HERMES_BASE_URL: return {'sent':False,'reason':'HERMES_BASE_URL not configured'}
    headers={'Content-Type':'application/json'}
    if HERMES_API_KEY: headers['X-API-Key']=HERMES_API_KEY
    for path in ('/v1/notifications','/v1/messages','/api/notifications'):
        try:
            r=requests.post(HERMES_BASE_URL+path,json=payload,headers=headers,timeout=5)
            if r.ok: return {'sent':True,'status_code':r.status_code,'path':path}
        except Exception: pass
    return {'sent':False,'reason':'No compatible HERMES notification endpoint accepted request'}
