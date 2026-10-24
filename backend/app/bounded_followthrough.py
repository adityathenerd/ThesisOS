"""Finite post-intake source attempts, batched facts, one reassessment per delta."""
import copy,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from pydantic import BaseModel,ConfigDict,Field
from .scouting_loop import ScoutingLoop,RunStore,LoopStopped,company_linked_current_roles
from .agent_bridge import comparison_packet
from .models import Evidence
from .research_ingest import accept_research
from .settings import APP_ROOT
from .state import now,uid
from .errors import ServiceError

class StartFollowThrough(BaseModel):
    model_config=ConfigDict(extra='forbid')
    execute_live:bool
    idempotency_key:str=Field(min_length=1,max_length=120)

class FollowThroughStage(ScoutingLoop):
    def __init__(self,state,settings,pool):self.state,self.settings,self.pool=state,settings,pool;self.store=RunStore(state,'scouting_followthrough_stages')
    def for_parent(self,parent_id):return {'items':[p for p in self.store.list() if p['parent_run_id']==parent_id]}
    def process_intake_case(self,parent_id,case_id):
        """Same worker, one cumulative child budget across future intake cases."""
        stages=self.for_parent(parent_id)['items'];parent=RunStore(self.state).get(parent_id)
        if not stages:
            stage=self.start_stage(parent_id,StartFollowThrough(execute_live=True,idempotency_key=parent_id+':bounded-followthrough'),case_ids=[case_id],submit=False)
        else:
            stage=stages[0]
            if any(c['case_id']==case_id for c in stage['candidates']):return
            candidate=copy.deepcopy(next(c for c in parent['candidates'] if c.get('case_id')==case_id));candidate.update(stage='queued',intake_assessment_id=candidate.get('assessment_id'),source_attempts=[])
            self.store.change(stage['id'],lambda p:(p['candidates'].append(candidate),p.update(status='queued')))
        self._run_stage(stage['id'])
    def start_stage(self,parent_id,request,*,case_ids=None,submit=True):
        if not request.execute_live:raise ServiceError('live_execution_required','Explicit bounded follow-through execution is required',409)
        parent=RunStore(self.state).get(parent_id)
        if datetime.fromisoformat(parent['deadline'].replace('Z','+00:00'))<=datetime.now(timezone.utc):raise ServiceError('deadline_expired','Original scouting deadline is closed; no new stage allowance was inferred',409)
        candidates=[copy.deepcopy(c) for c in parent['candidates'] if c.get('case_id') in (case_ids or parent['completed_case_ids'])]
        if not candidates:raise ServiceError('invalid_transition','No saved intake cases are available for directed follow-through',409)
        with self.state.connection(write=True) as db:
            old=db.execute('SELECT payload FROM scouting_followthrough_stages WHERE idempotency_key=?',(request.idempotency_key,)).fetchone()
            if old:return self.store.projection(json.loads(old[0]))
            if db.execute("SELECT 1 FROM scouting_followthrough_stages WHERE status IN ('queued','running','stopping')").fetchone():raise ServiceError('run_active','A post-intake stage is already active',409)
            if submit and db.execute("SELECT 1 FROM scouting_runs WHERE status IN ('queued','running','stopping')").fetchone():raise ServiceError('run_active','Wait for the intake worker boundary before starting a separate stage',409)
            id=uid('followthrough');stamp=now()
            for c in candidates:c.update(stage='queued',intake_assessment_id=c.get('assessment_id'),source_attempts=[],completion_scope='Bounded post-intake investigation pending; not complete.')
            p={'id':id,'stage_kind':'bounded_post_intake_followthrough','parent_run_id':parent_id,'status':'queued','created_at':stamp,'updated_at':stamp,'deadline':parent['deadline'],'limits':{'max_provider_requests':8,'max_credits':20,'max_model_assessments':4,'max_new_cases':0,'public_urls_per_case':2},'max_concurrent':1,'attempts':[],'candidates':candidates,'completed_case_ids':[],'stop_requested':False,'stop_reason':None,'current_operation':None,'mandate_id':parent['mandate_id'],'task_id':None,'automatic_retries':0,'qualification_accepted':False,'outreach_sent':False,'authority':'Direct human request to continue bounded enrichment after intake; separate child budget, cached paid facts first, no discovery, original deadline.'}
            db.execute('INSERT INTO scouting_followthrough_stages VALUES (?,?,?,?,?,?)',(id,request.idempotency_key,'queued',json.dumps(p),stamp,stamp))
        if submit:self.pool.submit(self._run_stage,id)
        return self.store.projection(p)
    def _plan(self,parent,candidate,origin):
        path=APP_ROOT/'planning/agents/current-four-child-research-plan.json'
        if path.exists():
            plan=json.loads(path.read_text(encoding='utf-8-sig'))
            if plan['parent_run_id']==parent['id']:
                entry=next((e for e in plan['cases'] if e['case_id']==candidate['case_id']),None)
                if entry:
                    if entry['origin_assessment_ref']!=origin['id'] or entry['origin_input_ref']!=origin['result']['ref']:raise LoopStopped('directed_source_plan_origin_changed')
                    return entry
        # Future intakes use only actual hrefs in their saved public page.
        from html.parser import HTMLParser
        from urllib.parse import urljoin,urlsplit
        class Links(HTMLParser):
            def __init__(self):super().__init__();self.links=[]
            def handle_starttag(self,tag,attrs):
                if tag=='a' and dict(attrs).get('href'):self.links.append(dict(attrs)['href'])
        receipt=candidate.get('source_receipt',{});parser=Links();path=APP_ROOT/receipt.get('raw_path','missing')
        if path.is_file():parser.feed(path.read_text(encoding='utf-8',errors='replace'))
        question=origin['result']['assessment']['case_brief']['next_action'];domain=candidate['domain'];urls=[]
        for href in parser.links:
            url=urljoin('https://'+domain,href);p=urlsplit(url)
            if p.scheme=='https' and p.hostname in [domain,'www.'+domain] and p.path not in ['/',''] and not any(x in p.path.lower() for x in ['privacy','terms','contact','login','signup']) and url not in urls:urls.append(url)
        urls.sort(key=lambda u:sum(t in u.lower() for t in ['about','team','product','solution','doc','science','app']),reverse=True)
        return {'source_points':[{'id':'directed:'+candidate['case_id']+':'+str(i),'question':question,'investigation':{'query':url},'execution_owner':'backend child-stage worker'} for i,url in enumerate(urls[:2])],'parent_model_next_action':question}
    def _run_stage(self,id):
        terminal='completed';reason='bounded_followthrough_complete_human_questions_remain'
        try:
            self.store.check(id,170);self.store.change(id,lambda p:p.update(status='running',started_at=now()))
            stage=self.store.get(id);parent=RunStore(self.state).get(stage['parent_run_id'])
            ordered=sorted([c for c in stage['candidates'] if c['stage']=='queued'],key=lambda c:c['domain']=='labwren.com')
            for candidate in ordered:
                self.store.check(id,170);self._case(id,parent,candidate)
        except LoopStopped as exc:terminal='stopped';reason=str(exc)
        except Exception as exc:terminal='failed';reason='child_stage_error_'+type(exc).__name__+'_no_retry'
        finally:self.store.change(id,lambda p:p.update(status=terminal,stop_reason=reason,finished_at=now(),current_operation=None))
    def _case(self,id,parent,candidate):
        case_id=candidate['case_id'];context=self.state.load_assessment_context(case_id)
        with self.state.connection() as db:row=db.execute('SELECT id,payload FROM semantic_assessments WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)).fetchone()
        saved=json.loads(row['payload']);origin={'id':row['id'],'result':saved['result']};plan=self._plan(parent,candidate,origin)
        if saved['backend_versions']!=context.versions.model_dump(mode='json'):raise LoopStopped('case_changed_before_directed_plan_acceptance')
        self._candidate(id,candidate['key'],stage='directed_research',origin_assessment_id=row['id'],execution_input_ref=comparison_packet(context,output_tokens=0).ref.model_dump(mode='json'),source_plan=plan,remaining_public_attempts=2)
        packet=copy.deepcopy(context.research_context or {});observations=[];attempts=[];details=[]
        def add(claim,text,url,stamp,*,person=None,provider=False,kind='source_reported',limits=None):
            e=Evidence(id=uid('evidence'),company_id=context.company.id,claim_type=claim,summary=text,source_url=url,source_key=id+':'+case_id+':'+str(len(observations)),retrieved_at=stamp,data_mode='live');observations.append(e)
            packet.setdefault('subjects',{})[e.id]={'kind':'person','id':person} if person else {'kind':'company','id':context.company.id}
            packet.setdefault('observation_metadata',[]).append({'evidence_id':e.id,'assertion_kind':kind,'support_status':'supported','source_type':'backend_execution_receipt' if claim=='backend_recorded_research_attempts' else ('indexed_provider_report' if provider else ('observed_public_tool' if kind=='observed' else 'first_party_company_page')),'source_quality':'not_independently_verified','limitations':limits or ['Attributed bounded source; not independent proof of product operation, current contribution, ownership or efficacy.']});return e.id
        receipt=next((a for a in parent['attempts'] if a['intent']=='enrich:'+candidate['key']),None)
        if receipt:
            raw=json.loads((APP_ROOT/receipt['raw_path']).read_text(encoding='utf-8'));data=json.loads(raw['response_text'])[0]['matches'][0]['company_data'];group_ids=[]
            for lead in company_linked_current_roles(data,candidate['key']):
                person='person:crustdata:'+str(lead['person_id'])
                if any(p['id']==person for p in packet.get('people',[])):continue
                eid=add('cached_exact_company_role',lead['name']+' is indexed in an exact company-ID current employment record as '+lead['title']+'. This source-reported role does not establish founder status, implementation contribution, rights or independently verified currentness.','https://api.crustdata.com/company/enrich',raw['received_at'],person=person,provider=True)
                packet.setdefault('people',[]).append({'id':person,'name':lead['name']});packet.setdefault('relationships',[]).append({'id':'role:'+id+':'+str(lead['person_id']),'person_id':person,'company_id':context.company.id,'role':lead['title']+' (indexed source-reported current role; unverified)','status':'supported','evidence_ids':[eid]});group_ids.append(eid)
            if group_ids:
                ref=parent['id']+':enrich:'+candidate['key'];group=next((g for g in packet.setdefault('provider_response_groups',[]) if g['response_ref']==ref),None)
                if group:group['evidence_ids'].extend(group_ids)
                else:packet['provider_response_groups'].append({'response_ref':ref,'evidence_ids':group_ids})
                task='cached-role:'+case_id;attempts.append({'task_id':task,'question_id':'historical-parent:'+row['id'],'status':'succeeded','summary':'Exact already-paid company-linked role fields recovered from cached response; no provider call. Role identity remains distinct from contribution.','accepted_evidence_ids':group_ids,'source_urls':['https://api.crustdata.com/company/enrich'],'attempted_at':now()});details.append({'task_id':task,'raw_path':receipt['raw_path'],'original_received_at':raw['received_at'],'new_provider_calls':0})
        external=APP_ROOT/'backend/work/scouting-runs'/parent['id']/'external-followthrough'/(candidate['domain']+'.json')
        if external.exists():
            external_packet=json.loads(external.read_text(encoding='utf-8-sig'))
            if external_packet.get('case_id')!=case_id or external_packet['domain']!=candidate['domain'] or external_packet['new_public_page_visits']>2:raise LoopStopped('external_observation_scope_mismatch')
            for name,path in external_packet.get('proof_files',{}).items():
                if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=external_packet['proof_sha256'][name]:raise LoopStopped('external_observation_proof_changed')
            task='external-tool:'+case_id;self.store.reserve(id,'public',task,{'case_id':case_id,'public_page_attempts':external_packet['new_public_page_visits'],'source_url':external_packet['source_url']},seconds=20)
            ids=[add('observed_bounded_tool_workflow',text,external_packet['source_url'],external_packet['observed_at'],kind='observed',limits=external_packet['limitations']) for text in external_packet['observations']]
            self.store.settle(id,task,status='succeeded',receipt_path=str(external.relative_to(APP_ROOT)))
            attempts.append({'task_id':task,'question_id':'historical-parent:'+row['id'],'status':'succeeded','summary':'Actual root browser BCA starter workflow and three independent arithmetic checks observed; narrow scope and own-created workspace caveats retained.','accepted_evidence_ids':ids,'source_urls':[external_packet['source_url']],'attempted_at':external_packet['observed_at']});details.append({'task_id':task,**external_packet});self._candidate(id,candidate['key'],remaining_public_attempts=0)
        else:
            for index,point in enumerate(plan.get('source_points',[])[:2]):
                self.store.check(id,170);url=point['investigation']['query'];task='public:'+case_id+':'+str(index)
                self.store.reserve(id,'public',task,{'case_id':case_id,'origin_assessment_id':row['id'],'question':point['question'],'url':url},seconds=20)
                source=None;error=None
                try:source=self._source(id,SimpleNamespace(key=candidate['key'],canonical_domain=candidate['domain']),url)
                except (ValueError,OSError,Exception) as exc:
                    if isinstance(exc,LoopStopped):raise
                    error=type(exc).__name__+': '+str(exc)[:150]
                ids=[]
                prior_digests={r.get('sha256') for r in packet.get('source_fetch_receipts',[])}
                if source and source['sha256'] not in prior_digests:
                    ids=[add('directed_public_source_excerpt','Directed question: '+point['question']+' Public source excerpt (documentation/marketing, not a demonstrated workflow): '+source['excerpt'],source['url'],source['retrieved_at'])];packet.setdefault('source_fetch_receipts',[]).append({k:v for k,v in source.items() if k!='excerpt'})
                summary='Exact directed source fetched and new attributed text accepted; operational question may remain unresolved.' if ids else ('No new accepted material source text: '+(error or 'Same response as previously accepted source.'))
                status='succeeded' if ids else ('inaccessible' if error else 'no_answer');self.store.settle(id,task,status=status,source_receipt={k:v for k,v in (source or {}).items() if k!='excerpt'},error=error)
                attempts.append({'task_id':task,'question_id':point['id'],'status':status,'summary':summary,'accepted_evidence_ids':ids,'source_urls':[url],'attempted_at':now()});details.append({'task_id':task,'question':point['question'],'url':url,'summary':summary,'receipt':{k:v for k,v in (source or {}).items() if k!='excerpt'}})
                self._candidate(id,candidate['key'],remaining_public_attempts=1-index,source_attempts=copy.deepcopy(details))
        if not observations:
            self._candidate(id,candidate['key'],stage='human_handoff_no_material_delta',source_attempts=details,reason='Bounded source attempts yielded no accepted material delta; original assessment retained, no model call.');return
        # One combined acceptance after all directed attempts, then one fresh model.
        follow=packet.setdefault('follow_up',{});follow.update(pass_id=id,remaining_calls=0,capabilities=[]);follow.setdefault('attempts',[]).extend(attempts);follow.setdefault('attempt_details',[]).extend(details)
        packet.update(prior_assessment=origin['result']['assessment'],prior_ref=origin['result']['ref'],changed_evidence_ids=[e.id for e in observations]);packet['include_ecosystem_coverage']=True
        add('backend_recorded_research_attempts','Backend recorded actual bounded follow-through: '+json.dumps([{'task_id':a['task_id'],'status':a['status'],'summary':a['summary']} for a in attempts]),None,now())
        packet['changed_evidence_ids']=[e.id for e in observations]
        accept_research(self.state,case_id,observations,packet,expected_case_version=context.case.version)
        self._candidate(id,candidate['key'],stage='reassessing',material_delta_evidence_ids=[e.id for e in observations],source_attempts=details)
        self._assess(id,candidate['key'],case_id)
