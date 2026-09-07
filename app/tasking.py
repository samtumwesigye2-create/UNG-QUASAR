from __future__ import annotations
import os, requests

def _headers():
    h={}; k=os.getenv('ARGUS_API_KEY','').strip()
    if k: h['X-ARGUS-API-Key']=k
    return h

def _req(method,url,path,params=None):
    try:
        r=requests.request(method,f"{url.rstrip('/')}{path}",params=params,headers=_headers(),timeout=10); r.raise_for_status(); return {'ok':True,'data':r.json() if r.content else {}}
    except Exception as e: return {'ok':False,'error':str(e)}
def task_track_satellite(url,name,group='active',station_id='default'): return _req('POST',url,'/api/schedule',{'name':name,'group':group,'station_id':station_id,'use_radio':False,'use_rotator':False})
def task_watch_alerts(url,name,group='active',station_id='default'): return _req('POST',url,'/api/alerts/watch',{'name':name,'group':group,'station_id':station_id})
def task_get_passes(url,name,hours=24,station_id='default'): return _req('GET',url,'/api/passes',{'name':name,'hours':hours,'station_id':station_id})
def task_get_conjunctions(url,name,threshold_km=25.0): return _req('GET',url,'/api/conjunctions',{'name':name,'threshold_km':threshold_km})
def execute(url,action,params):
    if action=='track_satellite': return task_track_satellite(url,params['name'],params.get('group','active'),params.get('station_id','default'))
    if action=='watch_alerts': return task_watch_alerts(url,params['name'],params.get('group','active'),params.get('station_id','default'))
    if action=='get_passes': return task_get_passes(url,params['name'],params.get('hours',24),params.get('station_id','default'))
    if action=='get_conjunctions': return task_get_conjunctions(url,params['name'],params.get('threshold_km',25.0))
    return {'ok':False,'error':'Unsupported task action'}
