"""Normalize cached authorized research, accept once, then reassess once/case."""
import argparse,copy,hashlib,json,time
from pathlib import Path
from html.parser import HTMLParser
import httpx
from backend.batch_cases import current
from backend.app.models import Evidence
from backend.app.state import now
from backend.app.research_ingest import accept_research
from backend.app.agent_bridge import comparison_packet
from backend.app.agent_bridge import AgentAssessmentStore,ScriptedGraphTransport
from backend.app.batch import BatchStore
from backend.app.research_graph import saved_research_graph,record_research_decision,scout_result
from backend.app.follow_up import research_follow_up
from backend.app.enrichment_transport import EnrichmentTransport
from agents.brief import to_case_brief
from agents.models import MatcherResult
from agents.research_graph import (build_research_graph,ObservationGraphMetadata,EntitySpec,AssertionSpec,
    ResearchQuestion,ProviderResponseGroup,TopicInterestSpec)

ROOT=Path('backend/work/enrichment-pass')
ALIASES={'Peter Tippett MD PhD':'Peter Tippett','Michael Assiamah, MSW, MBA':'Michael Assiamah','Tess Marvin, PhD':'Tess Marvin','Frank Kischkel':'Frank C. Kischkel'}
POSTS={
 'replicate.health':[(0,'Chris Thomas discusses engineering infrastructure for software agents; this is professional commentary, not evidence that the healthcare product performs.'),(1,'Chris Thomas compares autonomous AI assistant tooling; this is attributed technical commentary, not a product benchmark or customer outcome.')],
 'caremesh.com':[(0,'Company reports Peter Tippett attending the 2026 Cleveland Clinic AI Summit and discussing the need to connect AI findings to actual care workflows.'),(1,'Company describes CONNECT message routing and delivery-management work when clinical messages fail to reach recipients.'),(2,'Company discusses reducing EHR inbox routing problems through accurate provider data and delivery rules.'),(3,'Company describes combining secure messaging, data formatting and alternative delivery channels in CONNECT.'),(4,'Company describes care-coordination and clinical-data exchange work; no operational outcome is independently validated.')],
 'swiftacare.com':[(0,'Michael Assiamah reports participating in the Global Leadership Exchange E-Mental Health Match and discusses technology and partnership access.'),(1,'Michael Assiamah reports Swiftacare and Support & Growth attendance/sponsorship at eMHIC25; this is an attributed event account, not evidence of customer outcomes.'),(2,'Michael Assiamah announces a planned eMHIC25 presentation about Swiftacare referral coordination; an organizer schedule is inspected separately.')],
 'neotargets.com':[(0,'Company discusses biomarker-based patient stratification and its target-discovery approach, without providing a new experimentally validated drug result.'),(1,'Company discusses oncology treatment side effects; cited general disease findings are not results for a NeoTargets asset.'),(2,'Company reports CEO Thomas Binzer and NeoTargets participation in a SwedenBIO assembly/executive dinner; co-presence does not establish personal ties.'),(3,'Company discusses combining AI with drug-discovery work; no new company experimental result is established by the post.'),(4,'Company announces an AffinityAI collaboration combining target-discovery and biological-validation capabilities with protein-design tools; executed asset results and rights remain unverified.')]
}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def short(value,n=450):return (value or '').strip()[:n]
def key(value):return hashlib.sha256(str(value).encode()).hexdigest()[:18]


class Intake:
    def __init__(self,state,candidate):
        self.state,self.candidate=state,candidate;self.case=state.detail(candidate['case_id']);self.context=state.load_assessment_context(self.case.id)
        self.packet=copy.deepcopy(self.context.research_context or {});self.new=[];self.changes=[];self.attempts=[];self.details=[];self.source_eids={};self.person_map={};self.counter=0
        self.packet.setdefault('provider_response_groups',[]);self.packet.setdefault('topic_interests',[])
        self.packet['include_ecosystem_coverage']=True
        with state.connection() as db:
            old=db.execute('SELECT id,payload FROM semantic_assessments WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(self.case.id,)).fetchone()
        self.prior_id=old['id'];self.prior=read_json=json.loads(old['payload'])['result']
        self.packet.update(prior_assessment=self.prior['assessment'],prior_ref=self.prior['ref'])
        self.qid='question:original:'+key(self.prior_id)
        for e in self.context.evidence:
            if e.source_url=='https://api.crustdata.com/company/search':
                # Exact shared discovery response, never distinct calls by URL.
                self.packet['provider_response_groups'].append({'response_ref':candidate['encounters'][0]['candidate']['discovery_refs']['execution_id'],'evidence_ids':[x.id for x in self.context.evidence if x.source_url==e.source_url]});break

    def add(self,claim,summary,*,url,stamp,person=None,mode='live',kind='source_reported',source_type='indexed_provider_report',source_quality='not_independently_verified',date=None,group=None,limits=None):
        self.counter+=1;eid='evidence:enrich:'+key(self.case.id)+':'+str(self.counter)
        e=Evidence(id=eid,company_id=self.case.company_id,claim_type=claim,summary=summary,source_url=url,source_key='enrichment:'+key((self.case.id,eid,url,summary)),observed_at=None,retrieved_at=stamp,data_mode=mode);self.new.append(e)
        self.packet.setdefault('subjects',{})[eid]={'kind':'person','id':person} if person else {'kind':'company','id':self.case.company_id}
        meta={'evidence_id':eid,'assertion_kind':kind,'support_status':'supported','source_type':source_type,'source_quality':source_quality,'publication_time':{'precision':'datetime' if 'T' in date else ('day' if len(date)==10 else 'year'),'value':date,'basis':'publication'} if date else {'precision':'unknown'},'limitations':limits or ['Provider/source claim; retrieval does not independently verify work, dates, rights or outcomes.']}
        if group:meta['original_source_id']=group
        self.packet.setdefault('observation_metadata',[]).append(meta);self.source_eids.setdefault(url,[]).append(eid);return eid

    def entity(self,id,kind,label,eids,**kw):
        existing=next((x for x in self.packet.setdefault('entities',[]) if x['id']==id),None)
        if existing:existing['evidence_ids']=list(dict.fromkeys(existing['evidence_ids']+eids));return id
        self.packet['entities'].append({'id':id,'kind':kind,'label':label[:240],'evidence_ids':eids,**kw});return id

    def edge(self,from_id,to_id,relation,label,eids,*,time=None,event=None,limitation='Explicit source-reported relation only; no friendship, endorsement, access or quality score is inferred.'):
        id='edge:enrich:'+key((self.case.id,from_id,to_id,relation,eids))
        self.packet.setdefault('assertions',[]).append({'id':id,'from_id':from_id,'to_id':to_id,'relation':relation,'label':label,'evidence_ids':eids,'assertion_kind':'source_reported','support_status':'supported','temporal_scope':time or {'precision':'unknown'},'limitation':limitation,'event_ref':event});return id

    def attempt(self,task,summary,urls,eids,status='succeeded',stamp=None):
        self.attempts.append({'task_id':task,'question_id':self.qid,'status':status,'summary':summary,'accepted_evidence_ids':eids,'source_urls':urls,'attempted_at':stamp})
        self.details.append({'task_id':task,'question_id':self.qid,'outcome':status,'summary':summary,'source_urls':urls,'attempted_at':stamp})

    def company(self,attempt,raw,data):
        assert str(data['crustdata_company_id'])==str(self.candidate['encounters'][0]['candidate']['provider_company_id'])
        basic=data.get('basic_info') or {};stamp=raw['received_at'];url='https://api.crustdata.com/company/enrich';eids=[]
        eids.append(self.add('provider_company_identity_context','Exact saved company ID enrichment reports '+json.dumps({k:basic.get(k) for k in ['name','primary_domain','year_founded','status','professional_network_url']})+'. These are indexed company fields; founding year/stage and current activity are not independently verified.',url=url,stamp=stamp))
        funding=data.get('funding') or {};facts={k:funding.get(k) for k in ['last_round_type','last_fundraise_date','total_investment_usd','investors']}
        if any(v is not None and v not in [[],0,0.0] for v in facts.values()):
            eid=self.add('provider_reported_financing_history','Provider reports historical financing '+json.dumps(facts)+'. Missing or zero values are not proof of no funding; this does not establish current stage, runway or YC backing.',url=url,stamp=stamp);eids.append(eid)
            for name in (funding.get('investors') or [])[:2]:
                oid=self.entity('org:reported-investor:'+key(name),'organisation',name,[eid]);self.edge(oid,self.case.company_id,'reported_investor_in','Provider reports historical investor',[eid])
        self.packet['provider_response_groups'].append({'response_ref':raw.get('request_id') or attempt['intent'],'evidence_ids':eids})
        self.attempt(attempt['intent'],'Exact company-ID enrichment received. Founder/operator profile leads were resolved separately; missing profiles/news are coverage gaps.',[url],eids,stamp=stamp)

    def person(self,selection,attempt,raw,data):
        assert data['crustdata_person_id']==selection['expected_person_id']
        name=selection['name'];alias=ALIASES.get(name,name);person=next((p['id'] for p in self.packet.get('people',[]) if p['name']==alias),None)
        if person is None:
            person='person:crustdata:'+str(data['crustdata_person_id']);self.packet.setdefault('people',[]).append({'id':person,'name':alias})
        self.person_map[data['crustdata_person_id']]=person
        roles=data.get('experience',{}).get('employment_details',{});matched=[(group,r) for group in ['current','past'] for r in roles.get(group,[]) if r.get('crustdata_company_id')==selection['expected_company_id']]
        if not matched:raise ValueError('Exact person ID does not supply the expected company link; do not attach ambiguous identity')
        url='https://api.crustdata.com/person/enrich';stamp=raw['received_at'];eids=[]
        eid=self.add('provider_resolved_person_identity','Indexed profile '+selection['profile_url']+' returns the exact selected person ID for '+alias+'. Employer history links this profile to the saved company ID. This joins provider records; it does not independently verify founder status, current role, work or identity.',url=url,stamp=stamp,person=person);eids.append(eid)
        used=[]
        for group,r in matched+[(g,r) for g in ['current','past'] for r in roles.get(g,[]) if r.get('crustdata_company_id')!=selection['expected_company_id']][:]:
            token=(r.get('name'),r.get('title'),r.get('start_date'),r.get('end_date'))
            if token in used or len(used)>=5:continue
            if not r.get('name') or r.get('name') in ['Self-employed','Stealth Startup']:continue
            used.append(token)
            facts={k:r.get(k) for k in ['name','title','start_date','end_date','description']};facts['description']=short(facts['description'],600)
            eid=self.add('provider_reported_work_history',alias+' indexed '+group+' role: '+json.dumps(facts)+'. Dates are provider-normalized and unverified; role description is attributable reported work, not independent execution proof.',url=url,stamp=stamp,person=person);eids.append(eid)
            cid=r.get('crustdata_company_id');oid=self.case.company_id if cid==selection['expected_company_id'] else self.entity('org:crustdata:'+str(cid) if cid else 'org:reported:'+key(r['name']),'organisation',r['name'],[eid],canonical_entity_ref={'kind':'crustdata_company','id':str(cid)} if cid else None)
            temporal={'precision':'interval','start':r['start_date'][:7] if r.get('start_date') else None,'end':r['end_date'][:7] if r.get('end_date') else None,'basis':'reported_as_of','limitation':'Provider-normalized dates; actual precision/currentness and chronology are unverified.'} if r.get('start_date') or r.get('end_date') else None
            self.edge(person,oid,'affiliated_with',('Reported '+group+' role: '+(r.get('title') or 'role unknown'))[:220],[eid],time=temporal)
            if cid==selection['expected_company_id']:
                rid='role:provider:'+key((person,token));self.packet.setdefault('relationships',[]).append({'id':rid,'person_id':person,'company_id':self.case.company_id,'role':r.get('title','Role unknown')+' ('+group+' in indexed profile; dates/source unverified)','status':'supported','evidence_ids':[eid]})
        summary=short(data.get('basic_profile',{}).get('summary'),900)
        if summary:
            eids.append(self.add('provider_attributable_professional_account',alias+' profile account: '+summary+' This is a provider-indexed self-description, not independently verified accomplishment or a personality/pedigree score.',url=url,stamp=stamp,person=person))
        for profile in (data.get('research_profiles') or [])[:1]:
            eids.append(self.add('unverified_academic_profile_link','Provider associates an academic profile named '+str(profile.get('name'))+' with '+alias+'. Affiliation/confidence: '+json.dumps({'affiliation':profile.get('affiliated_organisation'),'confidence':profile.get('confidence_score')})+'. Do not merge its authors/works into the ecosystem without primary attribution; citation totals are not founder merit.',url=url,stamp=stamp,person=person))
        self.packet['provider_response_groups'].append({'response_ref':raw.get('request_id') or attempt['intent'],'evidence_ids':eids})
        self.attempt(attempt['intent'],'Exact selected person ID and expected company-history link matched; current/past role distinction and unverified work/date limits preserved.',[selection['profile_url']],eids,stamp=stamp)
        self.changes.append('Accepted attributable indexed identity/work history for '+alias+'; title alone is not founder contribution proof.')

    def posts(self,attempt,raw,payload):
        domain=self.candidate['domain'];posts=payload.get('posts',[]);accepted=[];topic='topic:'+key(domain+':professional-content')
        for index,summary in POSTS.get(domain,[]):
            if index>=len(posts):continue
            post=posts[index];actor=post.get('actor') or {};pid=actor.get('crustdata_entity_id');person=self.person_map.get(pid) if actor.get('actor_type')=='person' else None
            if actor.get('actor_type')=='person' and person is None:continue
            if actor.get('actor_type')=='company' and str(pid)!=str(self.candidate['encounters'][0]['candidate']['provider_company_id']):raise ValueError('Post actor company mismatches saved identity')
            date=post.get('date_posted');url=post['share_url'];eid=self.add('indexed_professional_post',summary+' Aggregate engagement counts do not identify peers or validate the product. Publication time is reported by the cached index, not independently verified.',url=url,stamp=raw['received_at'],person=person,date=date,source_type='indexed_professional_post',group='source:post:'+key(post['share_urn']),limits=['Cached social record may be stale or date-normalized; post date does not establish event, reaction or relationship date.','Authorship/participation is attributed, not friendship, endorsement, customer proof or founder-quality scoring.']);accepted.append(eid)
            postid=self.entity('post:'+key(post['share_urn']),'post',actor.get('name','Unknown author')+' — '+summary[:130],[eid],canonical_entity_ref={'kind':'professional_network_post','id':post['share_urn']},attributes={'public_url':url,'share_urn':post['share_urn'],'author_type':actor.get('actor_type'),'aggregate_reactions':post.get('engagement',{}).get('total_reactions'),'aggregate_comments':post.get('engagement',{}).get('total_comments')},temporal_scope={'precision':'datetime','value':date,'basis':'publication','limitation':'Date as returned by cached index; unverified.'} if date else {'precision':'unknown'})
            self.edge(person or self.case.company_id,postid,'authored','Indexed authorship',[eid],time={'precision':'datetime','value':date,'basis':'publication','limitation':'Cached index publication date; not event/interaction date.'} if date else None)
            self.entity(topic,'topic',{'replicate.health':'Professional AI-agent engineering','caremesh.com':'Care workflow and interoperability','swiftacare.com':'Mental-health referral coordination','neotargets.com':'Oncology target discovery'}[domain],[eid]);self.edge(postid,topic,'posted_about','Explicit professional topic',[eid])
            if domain=='caremesh.com' and index==0:
                person=next(p['id'] for p in self.packet['people'] if p['name']=='Peter Tippett');event=self.entity('event:caremesh:2026-ai-summit','event','2026 Cleveland Clinic AI Summit (reported attendance)',[eid],temporal_scope={'precision':'year','value':'2026','basis':'event','limitation':'Only event year stated; September post date is not the event date.'});self.edge(postid,person,'mentions','Company post mentions founder',[eid]);self.edge(person,event,'participated_in','Company reports attendance',[eid],time={'precision':'year','value':'2026','basis':'event'},event=event)
            if domain=='neotargets.com' and index==4:
                org=self.entity('org:reported:affinityai','organisation','AffinityAI (named in company announcement)',[eid],canonical_entity_ref={'kind':'source_named_organisation','id':'AffinityAI / NeoTargets announcement'})
                project=self.entity('project:neotargets:affinityai-announcement','project','NeoTargets–AffinityAI announced collaboration',[eid],attributes={'status':'Company-reported announcement; execution/results/rights unverified'})
                for target in [org,project]:self.edge(postid,target,'mentions','Company announcement names collaboration',[eid])
                self.edge(self.case.company_id,org,'announced_partnership_with','Company announces collaboration',[eid],limitation='Source-reported partnership announcement only; no executed asset result, rights, founder access or friendship is inferred.')
                self.edge(org,project,'announced_participant','Named announced participant',[eid])
        self.attempt(attempt['intent'],'Bounded author-ID post search returned '+str(len(posts))+' indexed posts; accepted only relevant professional content. Empty results and irrelevant posts do not imply lack of activity or weak founders.',['https://api.crustdata.com/social_post/search'],accepted,status='succeeded' if accepted else 'no_answer',stamp=raw['received_at'])

    def public_sources(self,spec):
        for i,s in enumerate(spec.get('sources',[])):
            url=s['url'];stamp=spec.get('retrieved_at') or now();sourcekey=key(url);path=ROOT/('public-'+sourcekey+'.json')
            if path.exists():receipt=read(path)
            else:
                receipt={'url':url,'retrieved_at':stamp,'http_status':None}
                try:
                    r=httpx.get(url,timeout=20,follow_redirects=True,trust_env=False);receipt.update(http_status=r.status_code,final_url=str(r.url),sha256=hashlib.sha256(r.content).hexdigest());(ROOT/('public-'+sourcekey+'.raw')).write_bytes(r.content)
                except httpx.HTTPError as exc:receipt['error_kind']=type(exc).__name__
                path.write_text(json.dumps(receipt,indent=2))
            ids=[];person=next((p['id'] for p in self.packet.get('people',[]) if p['name']==s.get('person')),None)
            for claim in s['claims']:
                ids.append(self.add('targeted_public_followup',claim+' Limits: '+' '.join(s.get('limits',[])),url=url,stamp=receipt['retrieved_at'],person=person,mode='live' if receipt['http_status']==200 else 'captured',source_type='attributable_public_followup',group='source:public:'+sourcekey,date=s.get('publication_date'),limits=s.get('limits',[])))
            self.attempt('public-source:'+sourcekey,'Selected primary page inspected in public research; direct refetch status '+str(receipt['http_status'])+'. Claims remain scoped as documented.',[url],ids,stamp=stamp)
            if s.get('event') and person:
                e=s['event'];event=self.entity('event:public:'+sourcekey,'event',e['name'],ids,temporal_scope={'precision':'day','value':e['date'],'basis':'event','limitation':'Scheduled event, not proof of delivered talk.'});self.edge(person,event,'participated_in',e['role'],ids,time={'precision':'day','value':e['date'],'basis':'event'},event=event,limitation='Organizer lists a scheduled speaker; delivery and performance were not observed.')
        for a in spec.get('attempts',[]):self.attempt(a['id'],a['summary'],a.get('source_urls',[]),[],status=a['status'],stamp=spec.get('retrieved_at'))

    def primary_coauthors(self):
        if self.candidate['domain']!='neotargets.com':return
        julian=next(p['id'] for p in self.packet['people'] if p['name']=='Julian Walfridsson');andreas=next(p['id'] for p in self.packet['people'] if p['name']=='Andreas Höglund')
        topic='topic:neotargets:aml-dcps';supports={julian:[],andreas:[]};allids=[]
        for n,date in [(4,'2025-06-26'),(5,'2026-03-27')]:
            url=self.context.evidence[0].source_url
            s=read(Path('backend/work/scout-batch/neotargets.com/research-spec.json'))['sources'][n];url=s['url']
            eid=self.add('inspected_original_paper_authorship','Original publisher HTML citation_author metadata lists Julian Walfridsson and Andreas Höglund among authors, alongside Francesca Grassi and Madhurendra Singh. This supports coauthorship of this work, not company asset rights, personal friendship or sole invention.',url=url,stamp=now(),mode='captured',source_type='original_research_publisher_metadata',group='source:original-paper:'+key(url),date=date)
            allids.append(eid);self.entity(topic,'topic','AML/DCPS experimental target research',[eid])
            paper=self.entity('project:paper:'+key(url),'project','DCPS/AML original research '+date,[eid],temporal_scope={'precision':'day','value':date,'basis':'publication'})
            topic_edge=self.edge(paper,topic,'posted_about','Explicit scientific topic of joint work',[eid])
            for person in [julian,andreas]:
                authored=self.edge(person,paper,'coauthored','Publisher lists coauthor',[eid],time={'precision':'day','value':date,'basis':'publication'},event=paper);supports[person].extend([authored,topic_edge])
            for label in ['Francesca Grassi','Madhurendra Singh']:
                peer=self.entity('person:paper-author:'+key(label),'person',label,[eid],canonical_entity_ref={'kind':'source_named_author','id':label});self.edge(peer,paper,'coauthored','Publisher lists coauthor',[eid],time={'precision':'day','value':date,'basis':'publication'},event=paper)
            self.edge(julian,andreas,'coauthored_with','Joint original research authorship',[eid],time={'precision':'day','value':date,'basis':'publication'},event=paper)
        for person,edges in supports.items():
            self.packet['topic_interests'].append({'id':'interpretation:observed-work:'+key(person),'person_id':person,'topic_id':topic,'supporting_edge_ids':edges,'evidence_ids':allids,'temporal_scope':{'precision':'interval','start':'2025-06-26','end':'2026-03-27','basis':'reported_as_of'},'explanation':'Bounded observed professional-work pattern: coauthorship on two inspected original AML/DCPS publications. This is not personality, grit, friendship, asset ownership or clinical-validity inference.'})

    def targeted_packets(self):
        domain=self.candidate['domain']
        if domain=='caremesh.com':
            spec=read('C:/Users/ASUS/Documents/Codex/2026-10-24/new-chat/work/caremesh-follow-through.json')
            for s in spec['sources']:
                receipt=read(Path(spec['receipt_folder'])/(s['file_key']+'.receipt.json'));ids=[]
                for claim in s['claims']:
                    ids.append(self.add('inspected_workflow_or_deployment_record',claim+' Limits: '+' '.join(s['limits']),url=s['url'],stamp=receipt['retrieved_at'],date=s.get('publication_date'),source_type='hospital_hosted_implementation_account' if s['file_key'].startswith('hospital') else 'company_workflow_report',group='source:followup:'+key(s['url']),limits=s['limits']))
                self.attempt('caremesh-followup:'+s['file_key'],'Primary workflow/deployment document actually inspected; historical/current-page/anonymous-report limits preserved.',[s['url']],ids,stamp=receipt['retrieved_at'])
                if s['file_key']=='hospital-announcement':
                    org=self.entity('org:public:tampa-general-hospital','organisation','Tampa General Hospital',ids);event=self.entity('event:caremesh:tgh-usf-2020','event','2020 hospital/USF careMESH implementation account',ids,temporal_scope={'precision':'day','value':'2020-09-09','basis':'publication','limitation':'Announcement date; not a 2026 workflow test or NAVIGATE launch date.'})
                    self.edge(self.case.company_id,event,'described_implementation','Named implementation account',ids)
                    for name,title in [('Scott Arnold','CIO'),('Nishit Patel','CMIO')]:
                        person=self.entity('person:public:tgh:'+key(name),'person',name,ids,canonical_entity_ref={'kind':'source_named_institutional_counterparty','id':s['url']+'#'+name});self.edge(person,org,'affiliated_with','Hospital announcement identifies '+title,ids,time={'precision':'day','value':'2020-09-09','basis':'reported_as_of'},limitation='Role as reported in 2020; current tenure unknown. Not a founder/friend/investor inference.');self.edge(person,event,'quoted_in','Named institutional implementation counterparty',ids)
            self.changes.append('Added a hospital-hosted implementation account, currently served access instructions and an inspected detailed company workflow report; current performance/measurement method remain unresolved.')
        elif domain=='find-nuclei.com':
            spec=read(ROOT/'find-nuclei-follow-through.json');eid=self.add('observed_public_workflow',spec['claim']+' Observed Distance1 output:4040µm. Limits: '+' '.join(spec['limits']),url=spec['url'],stamp=spec['retrieved_at'],kind='observed',source_type='backend_observed_public_browser_workflow',source_quality='one_worked_example_not_benchmark',group='source:viewer-test:'+key(self.case.id),limits=spec['limits'])
            self.attempt('find-nuclei-public-viewer-workflow','Opened official viewer and one public IDR sample, observed rendered fluorescence image and a two-click distance annotation. No calibration/accuracy/customer test.',[spec['url'],spec['sample_url']],[eid],stamp=spec['retrieved_at']);self.changes.append('Actually exercised one publicly available viewer/sample/annotation workflow; no founder, rights or scientific accuracy claim inferred.')
        elif domain=='cadexgenomics.com':
            spec=read('planning/investment-thesis/batch-evidence/cadex-follow-through.json')
            for a in spec['attempts']:
                eid=None
                if a.get('url'):eid=self.add('recorded_public_report_access_attempt','Research collaborator recorded: '+a['outcome']+' This is an access/search outcome, not evidence that the report is absent or the science/company failed.',url=a['url'],stamp=spec['completed_at_utc'],mode='captured',kind='observed',source_type='recorded_public_research_attempt',source_quality='access_status_only',group='source:research-attempt:'+key(a['id']),limits=['No full original study report was inspected; do not import indexed abstract results or author/program linkage.'])
                self.attempt(a['id'],a['outcome'],[a['url']] if a.get('url') else [],[eid] if eid else [],status='inaccessible' if a.get('url') else 'no_answer',stamp=spec['completed_at_utc'])
            self.changes.append('The decisive full-report lookup was actually attempted without an inspectable report; new source-reported leadership end dates and exact human report questions are preserved.')
        elif domain=='aphoticbio.com':
            # Existing primary repository/article explicitly attributes this work.
            tess=next(p['id'] for p in self.packet['people'] if p['name']=='Tess Marvin');eid='evidence:aphoticbio-com:4:0'
            peer=self.entity('person:source:yun-hao','person','Yun Hao',[eid],canonical_entity_ref={'kind':'source_named_research_author','id':'Yun Hao / DISCERN doctoral research'})
            work=self.entity('project:aphotic:discern-doctoral-work','project','DISCERN doctoral research (company technical account)',[eid])
            self.edge(tess,work,'coauthored','Source attributes co-first-authored research',[eid],event=work);self.edge(peer,work,'coauthored','Source attributes co-first-authored research',[eid],event=work);self.edge(tess,peer,'coauthored_with','Reported co-first authorship',[eid],event=work,limitation='Company technical account, supported by linked academic artifact; personal relationship, sole authorship and commercial rights are not established.')

    def finish(self):
        domain=self.candidate['domain']
        outcome='Bounded follow-through execution history (operational outcomes, not negative company evidence): '+json.dumps([{'task':a['task_id'],'status':a['status'],'summary':a['summary']} for a in self.attempts])
        receipt_eid=self.add('backend_recorded_research_attempts',outcome,url=None,stamp=now(),kind='observed',mode='captured',source_type='backend_research_execution_receipts',source_quality='actual_bounded_attempt_history',group='source:backend-attempts:'+key(self.case.id),limits=['No answer/access failure in these sources is not proof of nonexistence, scientific failure or weak founders.','Attempts at identity lookup, public workflow inspection and clinical report access have different scopes; they do not substitute for each other.'])
        self.packet['changed_evidence_ids']=[e.id for e in self.new]
        basis={'track':self.candidate['tracks'][0],'identity_and_scope':{'status':'supported','explanation':'Exact existing company ID/domain and inspected product/program sources place this comparison in the stated health/bioscience track. Current financing stage and wider novelty remain separate risks.','evidence_ids':[self.new[0].id]},'artifact_basis':{'find-nuclei.com':'hands_on_workflow','neotargets.com':'inspected_experiment','cadexgenomics.com':'source_claim_only','therapyselect.de':'source_claim_only','aphoticbio.com':'source_claim_only'}.get(domain,'inspected_documentation'),'material_contradictions':[],'remaining_risks':['Current stage/backing, current execution and source freshness need human judgment where unresolved.','Profile history/social activity is source-reported and cannot establish product performance, rights, friendship or founder grit.']}
        self.packet['follow_up']={'pass_id':'existing-nine-enrichment-v1','origin_assessment_id':self.prior_id,'questions':[{'id':self.qid,'criterion_ids':[],'question':self.prior['assessment']['case_brief']['decisive_doubt']['text'],'decision_consequence':self.prior['assessment']['stop_or_reopen_condition'],'what_to_obtain':self.prior['assessment']['case_brief']['next_action'],'evidence_ids':self.prior['assessment']['case_brief']['decisive_doubt']['evidence_ids'],'investigation':None}],'attempts':self.attempts,'attempt_details':self.details,'readiness_basis':basis,'remaining_calls':0,'capabilities':[],'execution_scope_status':'This bounded collection is complete. No more source actions or reassessment loops are advertised; unresolved current questions go to the human.'}
        self.packet.setdefault('limitations',[]).extend(['Enrichment is bounded to selected profiles/posts; missing records are not proof of missing work or weak founders.','Observed ecosystem is a sourced sample, not the full network. No friendship, endorsement, access, density or grit score is inferred.'])
        simulated=self.context.model_copy(update={'case':self.context.case.model_copy(update={'version':self.case.version+1}),'evidence':tuple(self.context.evidence)+tuple(self.new),'research_context':self.packet})
        packet=comparison_packet(simulated,output_tokens=0)
        graph=build_research_graph(packet,generated_at=now(),observation_metadata=[ObservationGraphMetadata.model_validate(x) for x in self.packet['observation_metadata']],entities=[EntitySpec.model_validate(x) for x in self.packet['entities']],assertions=[AssertionSpec.model_validate(x) for x in self.packet['assertions']],questions=[ResearchQuestion.model_validate(x) for x in self.packet.get('questions',[])],provider_response_groups=[ProviderResponseGroup.model_validate(x) for x in self.packet['provider_response_groups']],topic_interests=[TopicInterestSpec.model_validate(x) for x in self.packet.get('topic_interests',[])],include_ecosystem_coverage=True,limitations=self.packet['limitations'])
        bundle={'case_id':self.case.id,'domain':domain,'expected_case_version':self.case.version,'origin_assessment_id':self.prior_id,'observations':[e.model_dump(mode='json') for e in self.new],'packet':self.packet,'material_delta':self.changes,'preflight_graph_id':graph.graph_id,'preflight_entities':len(graph.nodes),'preflight_edges':len(graph.edges)}
        folder=ROOT/domain;folder.mkdir(exist_ok=True);(folder/'intake.json').write_text(json.dumps(bundle,indent=2),encoding='utf-8');return bundle


def normalize():
    _,state,_,batch=current();ledger=read(ROOT/'ledger.json')['attempts'];selection=read(ROOT/'person-selection.json');selected={p['expected_person_id']:p for p in selection}
    for candidate in batch['candidates']:
        if candidate['stage']!='complete':continue
        intake=Intake(state,candidate)
        for attempt in ledger:
            if attempt['case_id']!=candidate['case_id']:continue
            raw=read(attempt['raw_path'])
            if raw.get('http_status')!=200:continue
            payload=json.loads(raw['response_text']);route=attempt['route']
            if route=='/company/enrich':intake.company(attempt,raw,payload[0]['matches'][0]['company_data'])
            elif route=='/person/enrich':
                d=payload[0]['matches'][0]['person_data'];intake.person(selected[d['crustdata_person_id']],attempt,raw,d)
            elif route=='/person/search':intake.attempt(attempt['intent'],'Indexed people search returned '+str(len(payload.get('profiles',[])))+' bounded profiles; identities were selected separately. Zero/limited results are not proof of no relevant people.',['https://api.crustdata.com/person/search'],[],status='succeeded' if payload.get('profiles') else 'no_answer',stamp=raw['received_at'])
        # Person identity must precede authored-post mapping, regardless ledger order.
        for attempt in ledger:
            if attempt['case_id']!=candidate['case_id'] or attempt['route']!='/social_post/search':continue
            raw=read(attempt['raw_path']);intake.posts(attempt,raw,json.loads(raw['response_text']))
        for attempt in ledger:
            if attempt['case_id']!=candidate['case_id'] or not attempt['route'].endswith('#engagement'):continue
            raw=read(attempt['raw_path']);posts=json.loads(raw['response_text']).get('posts',[])
            if any(len(p.get('reactors',[]))>20 or len(p.get('comments',[]))>10 for p in posts):raise ValueError('Post arrays exceed approved bounds')
            # Account returned no individual arrays in all six selected snapshots.
            if any(p.get('reactors') or p.get('comments') for p in posts):raise ValueError('New peer data requires explicit identity normalization before graph ingestion')
            intake.attempt(attempt['intent'],'Exact-post bounded engagement lookup returned no named reactor/comment records despite aggregate counts. Individual interaction coverage remains unknown; no ties invented.',['https://api.crustdata.com/social_post/search'],[],status='no_answer',stamp=raw['received_at'])
        public=ROOT/(candidate['domain']+'.public-followup.json')
        if public.exists():intake.public_sources(read(public))
        intake.targeted_packets()
        intake.primary_coauthors()
        bundle=intake.finish();print(json.dumps({'domain':candidate['domain'],'new_observations':len(bundle['observations']),'nodes':bundle['preflight_entities'],'edges':bundle['preflight_edges'],'status':'intake_preflight_passed'}),flush=True)


def ingest():
    _,state,store,b=current()
    for candidate in b['candidates']:
        if candidate['stage']!='complete':continue
        folder=ROOT/candidate['domain'];out=folder/'accepted.json'
        if out.exists():continue
        bundle=read(folder/'intake.json')
        packet_id=accept_research(state,bundle['case_id'],[Evidence.model_validate(e) for e in bundle['observations']],bundle['packet'],expected_case_version=bundle['expected_case_version'])
        context=state.load_assessment_context(bundle['case_id']);receipt={'case_id':bundle['case_id'],'domain':candidate['domain'],'prior_assessment_id':bundle['origin_assessment_id'],'prior_case_version':bundle['expected_case_version'],'case_version':context.case.version,'research_packet_id':packet_id,'new_observations':len(bundle['observations']),'backend_versions':context.versions.model_dump(mode='json'),'accepted_at':now()}
        out.write_text(json.dumps(receipt,indent=2));saved_research_graph(state,bundle['case_id'])
        workflow=research_follow_up(state,bundle['case_id']);assert workflow['workflow']['state']=='reassessment_required'
        store.candidate_update(candidate['id'],enrichment_stage='reassessment_required',enrichment_case_version=context.case.version,enrichment_new_observations=len(bundle['observations']))
        print(json.dumps(receipt),flush=True)
    store.update(b['id'],enrichment_pass={'id':'existing-nine-enrichment-v1','status':'accepted_evidence_reassessment_required','collection_closed':True,'paid_source_credits':read(ROOT/'ledger.json')['actual_or_conservative_reserved_credits'],'max_reassessments':9,'prompt_version':'0.3'})


def reassess(domain):
    settings,state,store,b=current();folder=ROOT/domain;receipt_path=folder/'reassessment.json';accepted=read(folder/'accepted.json')
    if receipt_path.exists():print(json.dumps({'domain':domain,'existing_attempt':True,'status':read(receipt_path)['status']}));return
    # Start-Process is not a lifespan-ready barrier. Never create a running
    # invocation until startup recovery has completed on the serving process.
    require_runtime_ready()
    context=state.load_assessment_context(accepted['case_id'])
    if context.versions.model_dump(mode='json')!=accepted['backend_versions']:raise ValueError('Accepted material snapshot changed before reserved reassessment')
    transport_ledger=EnrichmentTransport(settings,ROOT)
    with transport_ledger.db() as db:
        db.execute('BEGIN IMMEDIATE');db.execute('CREATE TABLE IF NOT EXISTS model_attempts (case_id TEXT PRIMARY KEY,payload TEXT)')
        if db.execute('SELECT 1 FROM model_attempts WHERE case_id=?',(context.case.id,)).fetchone():raise ValueError('One reassessment already reserved; no automatic retry')
        if db.execute('SELECT COUNT(*) FROM model_attempts').fetchone()[0]>=9:raise ValueError('Nine reassessments cap reached')
        db.execute('INSERT INTO model_attempts VALUES (?,?)',(context.case.id,json.dumps({'status':'reserved','domain':domain,'case_version':context.case.version,'created_at':now()})))
    from agents.prompts import PROMPT_VERSION
    if PROMPT_VERSION!='0.3':raise ValueError('Prompt freeze changed; do not execute unreviewed version')
    packet=comparison_packet(context,output_tokens=6500);invocation=state.begin_assessment(context)
    receipt={'status':'started','domain':domain,'case_id':context.case.id,'invocation_id':invocation,'prior_assessment_id':accepted['prior_assessment_id'],'case_version':context.case.version,'context':packet.model_dump(mode='json'),'model_attempts':1}
    receipt_path.write_text(json.dumps(receipt,indent=2));started=time.perf_counter();transport=ScriptedGraphTransport(timeout_seconds=170,live_authorized=True)
    try:
        result=transport.invoke(packet);receipt.update(result=result.model_dump(mode='json'),metadata=transport.last_metadata);receipt_path.write_text(json.dumps(receipt,indent=2))
        if result.assessment is None or result.assessment.case_brief is None:raise ValueError('No valid rich reassessment/brief; paid output preserved, no retry')
        aid=AgentAssessmentStore(state).record(context,invocation,packet,result,provenance='compiled_graph_live_enrichment_reassessment')
        receipt.update(status='stored_genuine_result',assessment_id=aid)
    except Exception as exc:
        state.record_assessment_failure(invocation,'enrichment_reassessment_failed','Bounded reassessment failed; paid output retained where available. No retry or fallback.')
        receipt.update(status='failed',safe_error=str(exc)[:300])
    receipt['elapsed_seconds']=round(time.perf_counter()-started,3);receipt_path.write_text(json.dumps(receipt,indent=2))
    with transport_ledger.db() as db:db.execute('UPDATE model_attempts SET payload=? WHERE case_id=?',(json.dumps({k:v for k,v in receipt.items() if k not in ['context','result']}),context.case.id))
    if receipt['status']=='stored_genuine_result':finalize(domain)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['context','result']}),flush=True)


def require_runtime_ready():
    for _ in range(20):
        try:
            r=httpx.get('http://127.0.0.1:8000/api/v1/runtime/status',timeout=1,trust_env=False)
            if r.status_code==200 and r.json().get('lifespan_ready') is True:return r.json()
        except (httpx.HTTPError,ValueError):pass
        time.sleep(.25)
    raise ValueError('Serving lifespan is not ready; no model reservation/invocation/call created')


def finalize(domain):
    _,state,store,b=current();folder=ROOT/domain;r=read(folder/'reassessment.json');result=MatcherResult.model_validate(r['result']);aid=r['assessment_id'];case_id=r['case_id']
    if r['status']!='stored_genuine_result':raise ValueError('No stored genuine reassessment')
    projection=to_case_brief(result,assessment_ref=aid);BatchStore(state).save_brief(case_id,aid,projection.model_dump(mode='json'))
    record_research_decision(state,case_id,aid,decision_consequence=result.assessment.stop_or_reopen_condition)
    graph=saved_research_graph(state,case_id);workflow=research_follow_up(state,case_id)
    (folder/'research-graph.json').write_text(json.dumps(graph,indent=2));(folder/'scout-result.json').write_text(json.dumps(scout_result(state,case_id),indent=2));(folder/'research-follow-up.json').write_text(json.dumps(workflow,indent=2))
    with state.connection(write=True) as db:db.execute('UPDATE case_assessment_state SET pending=0,last_error=NULL,updated_at=? WHERE case_id=?',(now(),case_id))
    candidate=next(c for c in b['candidates'] if c['case_id']==case_id);store.candidate_update(candidate['id'],enrichment_stage='complete',enrichment_assessment_id=aid,latest_graph_id=graph['graph_id'],research_state=workflow['workflow']['state'],research_posture=projection.brief.research_posture)
    print(json.dumps({'domain':domain,'case_id':case_id,'status':'reassessed_and_saved','assessment_id':aid,'research_state':workflow['workflow']['state'],'posture':projection.brief.research_posture}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['normalize','ingest','reassess','finalize']);p.add_argument('domain',nargs='?');p.add_argument('--execute',action='store_true');args=p.parse_args()
    if args.stage=='reassess' and not args.execute:p.error('Explicit paid reassessment stage requires execute')
    if args.stage in ['normalize','ingest']:{'normalize':normalize,'ingest':ingest}[args.stage]()
    else:{'reassess':reassess,'finalize':finalize}[args.stage](args.domain)
