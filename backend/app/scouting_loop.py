"""A single durable, bounded discovery/research worker. No retries or outreach."""
import hashlib,ipaddress,json,socket,threading,time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict,replace
from datetime import datetime,timedelta,timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,urljoin
import httpx
from pydantic import BaseModel,ConfigDict,Field,StrictInt
from .agent_bridge import comparison_packet,ScriptedGraphTransport,AgentAssessmentStore
from .batch import BatchStore
from .discovery import CompanyCatalog,CompiledDiscovery,DiscoveryApproval,DiscoveryStore,ApprovedCompanySearchProvider,compile_discovery
from .errors import ServiceError
from .models import CreateMandate,Evidence
from .research_ingest import accept_research
from .research_graph import saved_research_graph,record_research_decision
from .follow_up import research_follow_up
from .settings import APP_ROOT
from .state import now,uid
from agents.brief import to_case_brief


class StartScoutingRun(BaseModel):
    model_config=ConfigDict(extra='forbid')
    execute_live:bool
    idempotency_key:str=Field(min_length=1,max_length=120)
    duration_minutes:StrictInt=Field(default=30,ge=1,le=30)
    max_new_cases:StrictInt=Field(default=4,ge=1,le=4)
    max_provider_requests:StrictInt=Field(default=20,ge=1,le=20)
    max_credits:StrictInt=Field(default=50,ge=1,le=50)
    max_model_assessments:StrictInt=Field(default=4,ge=1,le=4)


class LoopStopped(Exception):pass
class CandidateDeferred(Exception):pass

PLAN_PATH=APP_ROOT/'config/continuous-scout-plan.json'


class RunStore:
    def __init__(self,state):self.state=state
    @staticmethod
    def projection(p):
        providers=[a for a in p['attempts'] if a['kind']=='provider'];models=[a for a in p['attempts'] if a['kind']=='model']
        return {**p,'usage':{'provider_requests':len(providers),'known_actual_credits':round(sum(a.get('actual_microcredits') or 0 for a in providers)/1000000,6),'actual_credit_usage_complete':all(a.get('actual_microcredits') is not None for a in providers),'actual_or_reserved_credits':round(sum(a['actual_microcredits'] if a.get('actual_microcredits') is not None else a['quoted_microcredits'] for a in providers)/1000000,6),'model_attempts':len(models),'saved_assessments':sum(a['status']=='stored_genuine_result' for a in models),'new_cases':sum('case_id' in c for c in p['candidates']),'completed_cases':len(p['completed_case_ids'])}}
    def get(self,id):
        with self.state.connection() as db:r=db.execute('SELECT payload FROM scouting_runs WHERE id=?',(id,)).fetchone()
        if not r:raise ServiceError('not_found','Scouting run not found',404)
        return self.projection(json.loads(r[0]))
    def list(self):
        with self.state.connection() as db:return [self.projection(json.loads(r[0])) for r in db.execute('SELECT payload FROM scouting_runs ORDER BY rowid DESC LIMIT 20')]
    def change(self,id,fn):
        with self.state.connection(write=True) as db:
            r=db.execute('SELECT payload FROM scouting_runs WHERE id=?',(id,)).fetchone()
            if not r:raise ServiceError('not_found','Scouting run not found',404)
            p=json.loads(r[0]);fn(p);p['updated_at']=now()
            db.execute('UPDATE scouting_runs SET status=?,payload=?,updated_at=? WHERE id=?',(p['status'],json.dumps(p),p['updated_at'],id))
        return p
    def check(self,id,seconds=0):
        p=self.get(id)
        remaining=(datetime.fromisoformat(p['deadline'].replace('Z','+00:00'))-datetime.now(timezone.utc)).total_seconds()
        if p['status'] not in ['queued','running'] or p.get('stop_requested'):raise LoopStopped('human_stop_requested')
        if remaining<=seconds:raise LoopStopped('deadline_reached_or_insufficient_time_for_next_operation')
        return remaining
    def reserve(self,id,kind,intent,request,quote=0,seconds=25):
        self.check(id,seconds)
        def reserve(p):
            if p.get('stop_requested') or p['status'] not in ['queued','running']:raise LoopStopped('human_stop_requested')
            if datetime.fromisoformat(p['deadline'].replace('Z','+00:00'))<=datetime.now(timezone.utc)+timedelta(seconds=seconds):raise LoopStopped('deadline_reached_or_insufficient_time_for_next_operation')
            if any(a['intent']==intent for a in p['attempts']):raise LoopStopped('intent_already_attempted_no_retry')
            if kind=='provider':
                used=sum(a.get('actual_microcredits') if a.get('actual_microcredits') is not None else a['quoted_microcredits'] for a in p['attempts'] if a['kind']=='provider')
                if sum(a['kind']=='provider' for a in p['attempts'])>=p['limits']['max_provider_requests'] or used+quote>p['limits']['max_credits']*1000000:raise LoopStopped('provider_request_or_credit_cap_reached')
            if kind=='model' and sum(a['kind']=='model' for a in p['attempts'])>=p['limits']['max_model_assessments']:raise LoopStopped('model_assessment_cap_reached')
            p['attempts'].append({'intent':intent,'kind':kind,'request':request,'status':'reserved','quoted_microcredits':quote,'actual_microcredits':None,'started_at':now()});p['current_operation']=intent
        self.change(id,reserve)
    def settle(self,id,intent,**values):
        def settle(p):
            a=next(a for a in p['attempts'] if a['intent']==intent);a.update(values,finished_at=now())
        self.change(id,settle)


class PaidTransport(httpx.BaseTransport):
    def __init__(self,store,run_id,intent,quote,inner=None):self.store,self.run_id,self.intent,self.quote=store,run_id,intent,quote;self.inner=inner or httpx.HTTPTransport(retries=0)
    def handle_request(self,request):
        if str(request.url.host)!='api.crustdata.com' or request.url.path not in ['/company/search','/company/enrich']:raise LoopStopped('unapproved_provider_route')
        body=json.loads(request.content);self.store.reserve(self.run_id,'provider',self.intent,{'route':request.url.path,'body':body},self.quote)
        folder=APP_ROOT/'backend/work/scouting-runs'/self.run_id;folder.mkdir(parents=True,exist_ok=True);path=folder/(hashlib.sha256(self.intent.encode()).hexdigest()[:20]+'.response.json')
        try:
            response=self.inner.handle_request(request);response.read()
            receipt={'http_status':response.status_code,'request_id':response.headers.get('x-request-id'),'credits_used':response.headers.get('x-credits-used'),'received_at':now(),'request':body,'response_text':response.text}
            path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
            actual=round(float(receipt['credits_used'])*1000000) if receipt['credits_used'] is not None else None
            self.store.settle(self.run_id,self.intent,status='received' if response.status_code==200 else 'http_failed',http_status=response.status_code,request_id=receipt['request_id'],actual_microcredits=actual,raw_path=str(path.relative_to(APP_ROOT)))
            if response.status_code!=200:raise LoopStopped('provider_http_'+str(response.status_code)+'_no_retry')
            if actual is None:raise LoopStopped('provider_usage_unknown_reservation_retained')
            if actual>self.quote:raise LoopStopped('provider_usage_exceeded_quote_stop_for_review')
            return response
        except httpx.HTTPError as exc:
            self.store.settle(self.run_id,self.intent,status='transport_failed',error_kind=type(exc).__name__)
            raise LoopStopped('provider_transport_failure_no_retry') from exc
    def close(self):self.inner.close()


class PublicText(HTMLParser):
    def __init__(self):super().__init__();self.skip=0;self.parts=[];self.description=''
    def handle_starttag(self,tag,attrs):
        if tag in ['script','style','noscript','svg']:self.skip+=1
        a=dict(attrs)
        if tag=='meta' and a.get('name','').lower()=='description':self.description=a.get('content','')
    def handle_endtag(self,tag):
        if tag in ['script','style','noscript','svg']:self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip():self.parts.append(data.strip())


def public_url(url,domain):
    p=urlsplit(url)
    if p.scheme!='https' or p.username or p.password or p.port not in [None,443] or p.hostname not in [domain,'www.'+domain]:raise ValueError('Exact public company domain required')
    addresses=socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('Public address required')
    return url


class ScoutingLoop:
    def __init__(self,state,settings):self.state,self.settings=state,settings;self.store=RunStore(state);self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='bounded-scout-loop')
    def recover(self):
        for p in self.store.list():
            if p['status'] in ['queued','running','stopping']:
                self.store.change(p['id'],lambda r:r.update(status='interrupted',stop_reason='process_restarted_no_automatic_retry',finished_at=now()))
    def start(self,request):
        if not request.execute_live:raise ServiceError('live_execution_required','Explicit live execution is required for the bounded run',409)
        if not self.settings.crustdata_api_key.strip():raise ServiceError('provider_not_configured','Server Crustdata credential is missing; no run started',503)
        from agents.prompts import PROMPT_VERSION
        if PROMPT_VERSION!='0.3':raise ServiceError('stale_version','Only frozen prompt0.3 is authorized for this run',409)
        payload=request.model_dump();id=uid('scout_run');stamp=now()
        with self.state.connection(write=True) as db:
            old=db.execute('SELECT payload FROM scouting_runs WHERE idempotency_key=?',(request.idempotency_key,)).fetchone()
            if old:
                p=json.loads(old[0])
                if p['start_request']!=payload:raise ServiceError('invalid_transition','Run key already binds a different exact request',409)
                return self.store.projection(p)
            if db.execute("SELECT 1 FROM scouting_runs WHERE status IN ('queued','running','stopping')").fetchone():raise ServiceError('run_active','One scouting loop is already active',409)
            p={'id':id,'status':'queued','created_at':stamp,'updated_at':stamp,'deadline':(datetime.now(timezone.utc)+timedelta(minutes=request.duration_minutes)).isoformat().replace('+00:00','Z'),'start_request':payload,'limits':{k:payload[k] for k in ['max_new_cases','max_provider_requests','max_credits','max_model_assessments']},'max_concurrent':1,'attempts':[],'candidates':[],'completed_case_ids':[],'stop_requested':False,'current_operation':None,'stop_reason':None,'mandate_id':None,'task_id':None,'model_prompt_version':'0.3','automatic_retries':0,'qualification_accepted':False,'outreach_sent':False,'novelty_status':'unknown_no_authoritative_known_company_universe'}
            db.execute('INSERT INTO scouting_runs VALUES (?,?,?,?,?,?)',(id,request.idempotency_key,'queued',json.dumps(p),stamp,stamp))
        self.pool.submit(self._run,id);return self.store.projection(p)
    def stop(self,id):
        def stop(p):
            if p['status'] in ['queued','running','stopping']:p.update(stop_requested=True,status='stopping',stop_reason='human_stop_requested')
        return self.store.change(id,stop)
    def _candidate(self,id,key,**values):
        def change(p):
            c=next(c for c in p['candidates'] if c['key']==key);c.update(values)
        self.store.change(id,change)
    def _source(self,id,candidate):
        self.store.check(id,20);domain=candidate.canonical_domain
        if not domain:raise ValueError('No resolved public domain')
        url='https://'+domain;folder=APP_ROOT/'backend/work/scouting-runs'/id;folder.mkdir(parents=True,exist_ok=True)
        self._candidate(id,candidate.key,source_attempt={'url':url,'attempted_at':now(),'status':'started'})
        with httpx.Client(timeout=httpx.Timeout(12,connect=4),trust_env=False,follow_redirects=False) as client:
            for _ in range(4):
                self.store.check(id,15);public_url(url,domain)
                with client.stream('GET',url,headers={'User-Agent':'ThesisOSResearch/0.1'}) as r:
                    if r.status_code in [301,302,303,307,308]:url=urljoin(url,r.headers.get('location',''));continue
                    chunks=[];size=0
                    for chunk in r.iter_bytes():
                        size+=len(chunk)
                        if size>1000000:raise ValueError('Public page exceeds bounded size')
                        chunks.append(chunk)
                    raw=b''.join(chunks);status=r.status_code;ctype=r.headers.get('content-type','')
                break
            else:raise ValueError('Company redirect bound exceeded')
        digest=hashlib.sha256(raw).hexdigest();path=folder/('public-'+digest[:18]+'.html');path.write_bytes(raw)
        self._candidate(id,candidate.key,source_attempt={'url':url,'attempted_at':now(),'http_status':status,'raw_path':str(path.relative_to(APP_ROOT)),'sha256':digest,'status':'received'})
        if status!=200 or not any(t in ctype.lower() for t in ['html','text/plain']):raise ValueError('Public homepage inaccessible or not text, HTTP '+str(status))
        parser=PublicText();parser.feed(raw.decode('utf-8',errors='replace'));text=' '.join(parser.parts)
        if any(t in text.lower()[:3000] for t in ['verify you are human','enable javascript and cookies','checking your browser','access denied','just a moment...']):raise ValueError('Public response is an access/challenge page, not usable company content')
        if len(text)<80:raise ValueError('Public page has insufficient readable content')
        return {'url':url,'retrieved_at':now(),'http_status':status,'raw_path':str(path.relative_to(APP_ROOT)),'sha256':digest,'excerpt':((parser.description+' | ') if parser.description else '')+text[:12000]}
    def _research(self,id,candidate,track,source,task_id):
        self.store.check(id,25);p=self.store.get(id)
        self.state.persist_discovery(task_id,[candidate]);case=next(c for c in self.state.cases(p['mandate_id']) if c.canonical_domain==candidate.canonical_domain)
        self._candidate(id,candidate.key,case_id=case.id,stage='researching',source_receipt={k:v for k,v in source.items() if k!='excerpt'})
        observations=[];people=[];roles=[];metadata=[];subjects={};groups=[]
        def add(claim,summary,url,group,person=None,stamp=None,provider=False):
            e=Evidence(id=uid('evidence'),company_id=case.company_id,claim_type=claim,summary=summary,source_url=url,source_key=id+':'+candidate.key+':'+claim+':'+str(len(observations)),retrieved_at=stamp or source['retrieved_at'],data_mode='live');observations.append(e)
            subjects[e.id]={'kind':'person','id':person} if person else {'kind':'company','id':case.company_id}
            meta={'evidence_id':e.id,'assertion_kind':'source_reported','support_status':'supported','source_type':'first_party_company_page' if claim=='public_company_page_excerpt' else 'indexed_provider_report','source_quality':'not_independently_verified','limitations':['Exact source excerpt/provider record; no independent performance, role currentness, ownership or efficacy verification.']}
            if not provider:meta['original_source_id']=group
            metadata.append(meta);return e.id
        add('public_company_page_excerpt','Observed public page text (source-authored, may include marketing/navigation; not validated product performance): '+source['excerpt'],source['url'],source['sha256'])
        if candidate.provider_company_id and str(candidate.provider_company_id).isdigit():
            body={'crustdata_company_ids':[int(candidate.provider_company_id)],'fields':['basic_info','people']};intent='enrich:'+candidate.key
            with httpx.Client(transport=PaidTransport(self.store,id,intent,2000000),timeout=20,trust_env=False) as client:
                response=client.post('https://api.crustdata.com/company/enrich',headers={'Authorization':'Bearer '+self.settings.crustdata_api_key.strip(),'x-api-version':'2025-11-01'},json=body)
            enriched=response.json();matches=enriched[0]['matches'] if isinstance(enriched,list) and enriched else []
            provider_receipt=next(a for a in self.store.get(id)['attempts'] if a['intent']==intent)
            provider_stamp=json.loads((APP_ROOT/provider_receipt['raw_path']).read_text())['received_at']
            data=next((m['company_data'] for m in matches if str(m.get('company_data',{}).get('crustdata_company_id'))==candidate.provider_company_id),None)
            if data:
                basic=data.get('basic_info',{})
                normalize=lambda x:str(x).lower().removeprefix('www.').rstrip('.')
                if basic.get('primary_domain') and normalize(basic['primary_domain'])!=normalize(candidate.canonical_domain):
                    self._candidate(id,candidate.key,stage='deferred_identity_unresolved',reason='Exact-ID enrichment domain conflicts with search/homepage identity; no combined attribution or model call.',enrichment_receipt=provider_receipt['raw_path'])
                    raise CandidateDeferred('exact_id_domain_mismatch')
                eid=add('indexed_company_enrichment','Provider exact-ID basic record: '+json.dumps({k:basic.get(k) for k in ['name','primary_domain','description','status']},ensure_ascii=False)[:5000],'https://api.crustdata.com/company/enrich',intent,stamp=provider_stamp,provider=True)
                group_eids=[eid];seen=set()
                for entry in (data.get('people',{}).get('founders',[])+data.get('people',{}).get('cxos',[])):
                    pid=entry.get('crustdata_person_id');name=entry.get('basic_profile',{}).get('name')
                    current=entry.get('experience',{}).get('employment_details',{}).get('current',[])
                    linked=next((x for x in current if str(x.get('employer_crustdata_company_id'))==candidate.provider_company_id),None)
                    if not pid or not name or not linked or pid in seen:continue
                    seen.add(pid);person='person:crustdata:'+str(pid);title=linked.get('title') or linked.get('job_title') or 'Indexed company-linked current role (title unspecified)'
                    peid=add('indexed_company_linked_role',name+' is indexed in an exact company-ID linked current employment record as '+title+'. Provider claim; dates and actual implementation remain unverified.','https://api.crustdata.com/company/enrich',intent,person,stamp=provider_stamp,provider=True)
                    people.append({'id':person,'name':name});roles.append({'id':'role:'+id+':'+str(pid),'person_id':person,'company_id':case.company_id,'role':title,'status':'supported','evidence_ids':[peid]});group_eids.append(peid)
                    if len(people)>=5:break
                groups.append({'response_ref':id+':'+intent,'evidence_ids':group_eids})
        context=self.state.load_assessment_context(case.id);search_eids=[e.id for e in context.evidence]
        groups.append({'response_ref':candidate.discovery_refs['execution_id'],'evidence_ids':search_eids})
        packet={'people':people,'relationships':roles,'subjects':subjects,'observation_metadata':metadata,'provider_response_groups':groups,'include_ecosystem_coverage':True,'source_fetch_receipts':[{k:v for k,v in source.items() if k!='excerpt'}],'questions':[{'id':'question:'+case.id+':intro','target_node_ids':[case.company_id],'criterion_ids':['C2','C4'],'question':'Which named builder can demonstrate the described work, contribution and next substantive milestone?','decision_consequence':'Carry unresolved private proof into human research; do not certify product operation or qualify.'}],'limitations':['Automatically bounded research intake of an indexed exact-company record and public text excerpt. No hands-on product/science validation, contact preparation, independent role verification or YC-universe check.','Track '+track+' is the discovery hypothesis, not an accepted company classification.']}
        packet['follow_up']={'pass_id':id,'remaining_calls':0,'capabilities':[],'attempts':[{'task_id':'source:'+case.id,'question_id':'question:intake:'+case.id,'status':'succeeded','summary':'Exact-domain public homepage text was fetched and accepted as attributed text; no functional demonstration or future model-directed question is claimed resolved.','accepted_evidence_ids':[observations[0].id],'source_urls':[source['url']],'attempted_at':source['retrieved_at']}],'attempt_details':[{'task_id':'source:'+case.id,'question_id':'question:intake:'+case.id,**{k:v for k,v in source.items() if k!='excerpt'}}]}
        accept_research(self.state,case.id,observations,packet,expected_case_version=case.version)
        return case.id
    def _assess(self,id,key,case_id):
        remaining=self.store.check(id,170);context=self.state.load_assessment_context(case_id);packet=comparison_packet(context,output_tokens=6500)
        intent='model:'+case_id;self.store.reserve(id,'model',intent,{'case_id':case_id,'case_version':context.case.version,'prompt_version':'0.3'},seconds=170)
        invocation=self.state.begin_assessment(context);folder=APP_ROOT/'backend/work/scouting-runs'/id;path=folder/(case_id+'.model.json');transport=ScriptedGraphTransport(timeout_seconds=min(160,int(remaining)-5),live_authorized=True)
        receipt={'invocation_id':invocation,'context':packet.model_dump(mode='json'),'status':'started','model_attempts':1};path.write_text(json.dumps(receipt,indent=2))
        try:
            result=transport.invoke(packet);receipt.update(result=result.model_dump(mode='json'),metadata=transport.last_metadata,status='response_received');path.write_text(json.dumps(receipt,indent=2))
            aid=AgentAssessmentStore(self.state).record(context,invocation,packet,result,provenance='bounded_continuous_scout_live')
            brief=to_case_brief(result,assessment_ref=aid)
            if brief is None:raise ValueError('Genuine result lacks a complete brief')
            BatchStore(self.state).save_brief(case_id,aid,brief.model_dump(mode='json'))
            record_research_decision(self.state,case_id,aid,decision_consequence=result.assessment.stop_or_reopen_condition)
            graph=saved_research_graph(self.state,case_id);receipt.update(status='stored_genuine_result',assessment_id=aid,graph_id=graph['graph_id']);path.write_text(json.dumps(receipt,indent=2))
            flow=research_follow_up(self.state,case_id);(folder/(case_id+'.follow-up.json')).write_text(json.dumps(flow,indent=2))
            self.store.settle(id,intent,status='stored_genuine_result',assessment_id=aid,metadata=transport.last_metadata,raw_path=str(path.relative_to(APP_ROOT)))
            self._candidate(id,key,stage='complete',assessment_id=aid,graph_id=graph['graph_id'],research_posture=brief.brief.research_posture,research_state=flow['workflow']['state'],research_points=flow['workflow']['human_research_points'],completion_scope='Bounded source intake and one genuine assessment saved; unresolved research remains explicit.')
            self.store.change(id,lambda p:p['completed_case_ids'].append(case_id))
            with self.state.connection(write=True) as db:db.execute('UPDATE case_assessment_state SET pending=0,last_error=NULL,updated_at=? WHERE case_id=?',(now(),case_id))
        except Exception as exc:
            self.state.record_assessment_failure(invocation,'scouting_loop_assessment_failed','Bounded live result/integration failed; cached response retained where received; no retry.')
            self.store.settle(id,intent,status='failed',error_kind=type(exc).__name__,raw_path=str(path.relative_to(APP_ROOT)))
            self._candidate(id,key,stage='assessment_failed',reason=type(exc).__name__)
            raise LoopStopped('model_or_acceptance_failure_no_retry') from exc
    def _run(self,id):
        task_id=None;reason='plan_exhausted';terminal='completed'
        try:
            self.store.check(id,25);self.store.change(id,lambda p:p.update(status='running',started_at=now()))
            mandate=self.state.create_mandate(CreateMandate(title='Bounded continuous scouting '+id[-8:],thesis_text='Human-authorized 30-minute maximum continuous health/bio scouting using the pinned v0.3 thesis. Maximum4new cases; research only, no qualification or outreach. Legacy target_count is a compatibility placeholder.',target_count=1,reference_status='user_supplied'))
            task,_=self.state.enqueue_run(mandate.id);self.state.start_task(task.id);task_id=task.id
            self.store.change(id,lambda p:p.update(mandate_id=mandate.id,task_id=task_id))
            compiled=json.loads(PLAN_PATH.read_text());catalog=CompanyCatalog.model_validate_json((APP_ROOT/'config/provider-catalog/company-search.json').read_text())
            self.store.change(id,lambda p:p.update(plan_path='config/continuous-scout-plan.json',plan_sha256=hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(),reference_sha256=self.state.reference_material.document_sha256))
            known=set()
            with self.state.connection() as db:
                for r in db.execute('SELECT source_key,canonical_domain FROM companies'):
                    known.add(r[0]);known.add(r[1])
                for r in db.execute('SELECT payload FROM scout_batch_candidates'):
                    c=json.loads(r[0]);known.add(c.get('domain'));known.update('crustdata:'+str(e['candidate'].get('provider_company_id')) for e in c.get('encounters',[]))
            known.discard(None)
            queues=[]
            for index,old in enumerate(compiled['branches']):
                self.store.check(id,25)
                branch=CompiledDiscovery.model_validate(old).branch.model_copy(update={'id':id+':branch:'+str(index),'mandate_id':mandate.id,'limit':20})
                c=compile_discovery(branch,catalog,self.state.reference_material)
                approval=DiscoveryApproval(id=id+':approval:'+str(index),mandate_id=mandate.id,branch_digest=c.branch_digest,request_digest=c.request_digest,catalog_digest=c.catalog_digest,scope='discovery_only',approved=True,reviewer='Explicit human continuous-scout run; reviewed four-track semantic plan reused with bounded20results, no new filters',lossy_filters_reviewed=False,max_calls=1,max_result_slots=20,max_quoted_microcredits=c.quoted_microcredits_ceiling)
                DiscoveryStore(self.state).register(c,approval,catalog)
                folder=APP_ROOT/'backend/work/scouting-runs'/id;folder.mkdir(parents=True,exist_ok=True);selector=folder/(str(index)+'.selection.json');selector.write_text(json.dumps({'approval_id':approval.id,'attempt_key':'only-attempt'}))
                provider=ApprovedCompanySearchProvider(replace(self.settings,provider_mode='live',crustdata_search_config=selector),self.state,transport=PaidTransport(self.store,id,'search:'+str(index),c.quoted_microcredits_ceiling))
                candidates=provider.discover(mandate,20,task_id=task_id);queue=deque()
                for rank,candidate in enumerate(candidates,1):
                    duplicate='crustdata:'+str(candidate.provider_company_id) in known or candidate.canonical_domain in known
                    stage='duplicate_prior_identity' if duplicate else ('deferred_no_domain' if not candidate.canonical_domain else 'queued_for_public_research')
                    self.store.change(id,lambda p,can=candidate,r=rank,st=stage:p['candidates'].append({'key':can.key,'company_name':can.company_name,'domain':can.canonical_domain,'track_hypothesis':branch.hypothesis.track,'rank':r,'stage':st,'discovery_refs':can.discovery_refs}))
                    if not duplicate:
                        known.add('crustdata:'+str(candidate.provider_company_id));known.add(candidate.canonical_domain)
                        if candidate.canonical_domain:queue.append(candidate)
                queues.append((branch.hypothesis.track,queue))
            while any(q for _,q in queues):
                self.store.check(id,170);p=self.store.get(id)
                selected=sum('case_id' in c for c in p['candidates'])
                if selected>=p['limits']['max_new_cases']:raise LoopStopped('new_case_cap_reached')
                for track,queue in queues:
                    if not queue:continue
                    self.store.check(id,170);p=self.store.get(id)
                    if sum('case_id' in c for c in p['candidates'])>=p['limits']['max_new_cases']:raise LoopStopped('new_case_cap_reached')
                    candidate=queue.popleft();self._candidate(id,candidate.key,stage='fetching_public_source')
                    try:source=self._source(id,candidate)
                    except (ValueError,httpx.HTTPError,OSError) as exc:
                        self._candidate(id,candidate.key,stage='deferred_public_source_unresolved',reason=str(exc)[:160]);continue
                    try:case_id=self._research(id,candidate,track,source,task_id)
                    except CandidateDeferred:continue
                    self._assess(id,candidate.key,case_id)
            reason='finite_reviewed_plan_exhausted_no_automatic_query_expansion'
        except LoopStopped as exc:reason=str(exc);terminal='stopped'
        except Exception as exc:reason='worker_error_'+type(exc).__name__+'_no_retry';terminal='failed'
        finally:
            if task_id:
                try:self.state.complete_task(task_id)
                except Exception:pass
            self.store.change(id,lambda p:p.update(status=terminal,stop_reason=reason,finished_at=now(),current_operation=None))
    def close(self):
        for p in self.store.list():
            if p['status'] in ['queued','running']:self.stop(p['id'])
        self.pool.shutdown(wait=True)
