"""Explicit bounded existing-case research transport with durable reservations.

No scheduler, discovery, retry, contact enrichment, or credential serialization.
Raw response is committed before any semantic parsing/identity matching.
"""
import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
import httpx
from .errors import ServiceError
from .state import now


class EnrichmentTransport:
    CAPS={'/company/enrich':9,'/person/search':9,'/person/enrich':18,'/social_post/search':9,'/social_post/search#engagement':6,'/web/enrich/live':18}

    def __init__(self,settings,folder,*,transport=None):
        self.settings,self.folder,self.transport=settings,Path(folder),transport
        self.folder.mkdir(exist_ok=True,parents=True)
        self.path=self.folder/'ledger.sqlite'
        self.catalog=json.loads((self.folder/'account-permissions.json').read_text())['payload']
        self.endpoints={e['path']:e for e in self.catalog['endpoints']}
        scope=self.folder/'scope.json'
        self.scope=json.loads(scope.read_text()) if scope.exists() else {'case_ids':[],'collection_closed':True}
        with self.db() as db:db.execute('CREATE TABLE IF NOT EXISTS attempts (intent TEXT PRIMARY KEY, route TEXT, quote INTEGER, actual INTEGER, status TEXT, created_at TEXT, started REAL, payload TEXT)')

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=10)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback();raise
        finally:db.close()

    def quote(self,route,body):
        endpoint=self.endpoints.get(route.split('#')[0],{})
        if endpoint.get('status')!='enabled':raise ServiceError('capability_unavailable','Account endpoint is not enabled; no paid call made',409)
        if route not in self.CAPS:raise ServiceError('resource_limit','Route is outside this bounded pass',409)
        if body.get('cursor') or body.get('page',1)!=1:raise ServiceError('resource_limit','No pagination authorized',409)
        fields=body.get('fields',[]);enabled=endpoint.get('fields',{}).get('enabled',[])
        if any(f not in enabled for f in fields):raise ServiceError('capability_unavailable','Selected field is not enabled',409)
        if any('contact' in f or 'phone' in f or 'email' in f for f in fields):raise ServiceError('resource_limit','Contact fields are outside this research pass',409)
        base=float(endpoint['base_credits'])
        premium=sum(float(p['credits']) for p in endpoint.get('premium_fields',[]) if any(f==p['field'] or f.startswith(p['field']+'.') for f in fields))
        if route=='/company/enrich':
            if len(body.get('crustdata_company_ids',[]))!=1 or len(body.keys()-{'crustdata_company_ids','fields'})>0:raise ServiceError('resource_limit','Exactly one existing company ID required',409)
            units=1
        elif route=='/person/enrich':
            if body.keys()-{'professional_network_profile_urls','fields'}:raise ServiceError('resource_limit','Only indexed selected-profile enrichment is authorized',409)
            if len(body.get('professional_network_profile_urls',[]))!=1:raise ServiceError('resource_limit','Exactly one resolved profile required',409)
            units=1
        elif route=='/person/search':
            if body.keys()-{'filters','fields','limit','sorts'}:raise ServiceError('resource_limit','Unapproved person-search parameter',409)
            units=body.get('limit',0)
            if not 1<=units<=5:raise ServiceError('resource_limit','Person search limit must be 1–5',409)
            def paths(v):
                if isinstance(v,dict):
                    if 'field' in v:yield v['field']
                    for x in v.values():yield from paths(x)
                elif isinstance(v,list):
                    for x in v:yield from paths(x)
            filtered=list(paths(body.get('filters')))
            premium+=sum(float(p['credits']) for p in endpoint.get('premium_filters',[]) if any(f==p['field'] or f.startswith(p['field']+'.') for f in filtered))
        elif route.startswith('/social_post/search'):
            if body.keys()-{'filters','fields','limit','sorts'}:raise ServiceError('resource_limit','Unapproved post-search parameter',409)
            units=body.get('limit',0)
            if not 1<=units<=5:raise ServiceError('resource_limit','At most five indexed posts per call',409)
            if route.endswith('#engagement'):
                if units!=1:raise ServiceError('resource_limit','One selected post per engagement request',409)
                text=json.dumps(body.get('filters'))
                if not all(x in text for x in ['share_urn','engagement.total_reactions','engagement.total_comments']):raise ServiceError('resource_limit','Selected engagement requires post identity and server count bounds',409)
            elif any(f.startswith(('reactors','comments')) for f in fields):raise ServiceError('resource_limit','Engagement arrays require separate bounded intent',409)
        else:
            units=len(body.get('urls',[]))
            if units!=1:raise ServiceError('resource_limit','One selected public URL per fetch',409)
        return round((base+premium)*units*1_000_000)

    def call(self,intent,route,body,*,case_id):
        quote=self.quote(route,body);rawpath=self.folder/(hashlib.sha256(intent.encode()).hexdigest()[:20]+'.response.json')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT payload FROM attempts WHERE intent=?',(intent,)).fetchone()
            if prior:
                old=json.loads(prior[0])
                if old['request']!=body or old['route']!=route:raise ServiceError('invalid_transition','Intent already binds a different exact request',409)
                if not rawpath.exists():raise ServiceError('attempt_incomplete','Prior attempt lacks response; no automatic retry',409)
                return json.loads(rawpath.read_text(encoding='utf-8'))
            if self.scope.get('collection_closed') or case_id not in self.scope.get('case_ids',[]):raise ServiceError('resource_limit','This pass is closed or the case is outside its explicit existing-company scope',409)
            count=db.execute('SELECT COUNT(*) FROM attempts WHERE route=?',(route,)).fetchone()[0]
            used=db.execute('SELECT COALESCE(SUM(COALESCE(actual,quote)),0) FROM attempts').fetchone()[0]
            if count>=self.CAPS[route] or used+quote>150_000_000:raise ServiceError('resource_limit','Research call/150-credit cap reached; no paid request made',409)
            receipt={'intent':intent,'case_id':case_id,'route':route,'request':body,'quote_credits':quote/1_000_000,'status':'reserved','created_at':now(),'raw_path':str(rawpath)}
            db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?)',(intent,route,quote,None,'reserved',now(),time.time(),json.dumps(receipt)))
        start=time.perf_counter();response=None
        try:
            with httpx.Client(transport=self.transport,timeout=httpx.Timeout(35,connect=8),trust_env=False,follow_redirects=False) as client:
                response=client.post('https://api.crustdata.com'+route.split('#')[0],headers={'Authorization':'Bearer '+self.settings.crustdata_api_key.strip(),'x-api-version':'2025-11-01'},json=body)
            # Credentials/request headers never enter disk or the public projection.
            saved={'intent':intent,'case_id':case_id,'request':body,'http_status':response.status_code,'request_id':response.headers.get('x-request-id'),'credits_used':response.headers.get('x-credits-used'),'received_at':now(),'response_text':response.text}
            rawpath.write_text(json.dumps(saved,indent=2),encoding='utf-8')
            receipt.update(status='received' if response.status_code==200 else 'http_failed',http_status=response.status_code,request_id=saved['request_id'],credits_used=saved['credits_used'])
            actual=round(float(saved['credits_used'])*1_000_000) if saved['credits_used'] is not None else None
        except httpx.HTTPError as exc:
            actual=None;receipt.update(status='transport_failed',error_kind=type(exc).__name__)
            saved={'intent':intent,'case_id':case_id,'http_status':None,'error_kind':type(exc).__name__,'received_at':now()}
            rawpath.write_text(json.dumps(saved,indent=2),encoding='utf-8')
        receipt['elapsed_seconds']=round(time.perf_counter()-start,3)
        with self.db() as db:db.execute('UPDATE attempts SET actual=?,status=?,payload=? WHERE intent=?',(actual,receipt['status'],json.dumps(receipt),intent))
        self.export()
        return saved

    def export(self):
        with self.db() as db:
            records=[json.loads(x[0]) for x in db.execute('SELECT payload FROM attempts ORDER BY rowid')]
            spent=db.execute('SELECT COALESCE(SUM(COALESCE(actual,quote)),0) FROM attempts').fetchone()[0]/1_000_000
        result={'incremental_credit_cap':150,'actual_or_conservative_reserved_credits':spent,'attempts':records,'automatic_retries':0,'contact_calls':0}
        (self.folder/'ledger.json').write_text(json.dumps(result,indent=2),encoding='utf-8');return result
