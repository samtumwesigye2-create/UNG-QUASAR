from __future__ import annotations
import hmac, os, requests
from fastapi import Header, HTTPException, Depends
from dataclasses import dataclass

LOCAL_API_KEY=os.getenv('QUASAR_API_KEY','').strip()
IAM_BASE_URL=os.getenv('IAM_BASE_URL','').rstrip('/')
IAM_AUDIENCE=os.getenv('QUASAR_IAM_AUDIENCE','ung-quasar')

ROLE_ORDER={'viewer':0,'analyst':1,'operator':2,'commander':3,'admin':4}

@dataclass
class Principal:
    subject:str
    role:str
    source:str

def _iam_introspect(token:str):
    if not IAM_BASE_URL: return None
    try:
        r=requests.post(f"{IAM_BASE_URL}/v1/auth/introspect",json={'token':token,'audience':IAM_AUDIENCE},timeout=4)
        if not r.ok: return None
        d=r.json()
        if not d.get('active'): return None
        roles=d.get('roles') or ([d.get('role')] if d.get('role') else [])
        role=max((str(x).lower() for x in roles if str(x).lower() in ROLE_ORDER), key=lambda x:ROLE_ORDER[x], default='viewer')
        return Principal(str(d.get('sub') or d.get('subject') or 'iam-user'),role,'iam')
    except Exception: return None

def current_principal(authorization:str=Header(default=''), x_quasar_api_key:str=Header(default='')) -> Principal:
    if not LOCAL_API_KEY and not IAM_BASE_URL:
        return Principal('local-dev','admin','local')
    if LOCAL_API_KEY and hmac.compare_digest(x_quasar_api_key or '',LOCAL_API_KEY):
        return Principal('service-key','admin','api-key')
    if authorization.lower().startswith('bearer '):
        p=_iam_introspect(authorization.split(' ',1)[1].strip())
        if p: return p
    raise HTTPException(401,'Authentication required')

def require_role(min_role:str):
    def dep(p:Principal=Depends(current_principal)):
        if ROLE_ORDER.get(p.role,-1) < ROLE_ORDER[min_role]:
            raise HTTPException(403,f'{min_role} role required')
        return p
    return dep
