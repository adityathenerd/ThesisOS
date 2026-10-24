import json,tempfile,unittest
from pathlib import Path
import httpx
from unittest.mock import patch
from backend.app.assessments import load_reference_material
from backend.app.research_graph import saved_research_graph
from pydantic import ValidationError
from backend.app.scouting_loop import ScoutingLoop,RunStore,StartScoutingRun,ResumeScoutingRun,PaidTransport,LoopStopped
from backend.app.settings import APP_ROOT,Settings
from backend.app.state import StateService
from backend.app.errors import ServiceError
from agents.models import Answer,Finding,SemanticAssessment,CaseBrief,MatcherResult

class DetachedPool:
    def __init__(self):self.calls=[]
    def submit(self,*args):self.calls.append(args)
    def shutdown(self,**kwargs):pass

class ScoutingLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=APP_ROOT/'backend/work');self.state=StateService(Path(self.temp.name)/'state.db');self.state.initialize()
        self.loop=ScoutingLoop(self.state,Settings(crustdata_api_key='SCRIPTED_NOT_A_REAL_KEY'));self.loop.pool.shutdown();self.loop.pool=DetachedPool();self.store=self.loop.store
    def tearDown(self):self.loop.close();self.temp.cleanup()
    def start(self,**kw):return self.loop.start(StartScoutingRun(execute_live=True,idempotency_key='SCRIPTED_LOOP_TEST',**kw))
    def test_caps_and_duration_cannot_expand(self):
        for key,value in [('duration_minutes',31),('max_new_cases',5),('max_provider_requests',21),('max_credits',51),('max_model_assessments',5)]:
            with self.assertRaises(ValidationError):StartScoutingRun(execute_live=True,idempotency_key='test',**{key:value})
        self.assertEqual(self.store.list(),[])
    def test_durable_idempotent_start_and_no_overlap(self):
        first=self.start();again=self.start();self.assertEqual(first['id'],again['id']);self.assertEqual(len(self.loop.pool.calls),1)
        with self.assertRaises(ServiceError):self.loop.start(StartScoutingRun(execute_live=True,idempotency_key='another'))
        self.assertEqual(len(self.store.list()),1)
    def test_stop_and_deadline_block_new_operations(self):
        r=self.start();self.loop.stop(r['id'])
        with self.assertRaises(LoopStopped):self.store.reserve(r['id'],'provider','no-call',{},1)
        self.store.change(r['id'],lambda p:p.update(status='running',stop_requested=False,deadline='2000-01-01T00:00:00Z'))
        with self.assertRaises(LoopStopped):self.store.reserve(r['id'],'model','no-model',{})
        self.assertEqual(self.store.get(r['id'])['attempts'],[])
    def test_conservative_credit_reservation_and_no_retry(self):
        r=self.start(max_credits=1);self.store.reserve(r['id'],'provider','one',{},600000)
        self.store.settle(r['id'],'one',status='transport_failed')
        self.assertFalse(self.store.get(r['id'])['usage']['actual_credit_usage_complete'])
        self.assertEqual(self.store.get(r['id'])['usage']['actual_or_reserved_credits'],.6)
        with self.assertRaises(LoopStopped):self.store.reserve(r['id'],'provider','two',{},600000)
        with self.assertRaises(LoopStopped):self.store.reserve(r['id'],'provider','one',{},100000)
    def test_raw_response_saved_before_any_json_normalization(self):
        r=self.start();calls=[]
        def handle(request):calls.append(request);return httpx.Response(200,headers={'x-credits-used':'.3'},content=b'not-json-success-response')
        transport=PaidTransport(self.store,r['id'],'search',600000,httpx.MockTransport(handle))
        with httpx.Client(transport=transport) as client:response=client.post('https://api.crustdata.com/company/search',json={'limit':20})
        with self.assertRaises(ValueError):response.json()
        attempt=self.store.get(r['id'])['attempts'][0];saved=json.loads((APP_ROOT/attempt['raw_path']).read_text());self.assertEqual(saved['response_text'],'not-json-success-response');self.assertEqual(attempt['actual_microcredits'],300000);self.assertEqual(len(calls),1)
    def test_provider_auth_failure_is_single_attempt(self):
        r=self.start();calls=[]
        def handle(request):calls.append(request);return httpx.Response(401,headers={'x-credits-used':'0'},text='blocked')
        with httpx.Client(transport=PaidTransport(self.store,r['id'],'auth-test',600000,httpx.MockTransport(handle))) as client:
            with self.assertRaises(LoopStopped):client.post('https://api.crustdata.com/company/search',json={'limit':20})
        self.assertEqual(len(calls),1);self.assertEqual(self.store.get(r['id'])['attempts'][0]['http_status'],401)
    def test_restart_marks_interrupted_without_dispatch(self):
        r=self.start();self.loop.recover();self.assertEqual(self.store.get(r['id'])['status'],'interrupted');self.assertEqual(len(self.loop.pool.calls),1)
    def test_quarantine_malformed_record_and_explicit_cached_continuation_without_paid_retry(self):
        r=self.start();calls=[]
        def handle(request):
            calls.append(request)
            return httpx.Response(200,headers={'x-credits-used':'.6'},json={'companies':[{'crustdata_company_id':991,'basic_info':{'name':'SCRIPTED VALID','primary_domain':'valid.example'}},{'crustdata_company_id':992,'basic_info':{'name':'','primary_domain':''}}]})
        body={'limit':20,'fields':['basic_info.name','basic_info.primary_domain','basic_info.description'],'search':{'query':'SCRIPTED TEST','mode':'hybrid'}}
        with httpx.Client(transport=PaidTransport(self.store,r['id'],'search:0',600000,httpx.MockTransport(handle))) as client:p=client.post('https://api.crustdata.com/company/search',json=body).json()
        self.assertEqual(len(p['companies']),1);report=self.store.get(r['id'])['normalization_reports']['search:0'];self.assertEqual(report['original_returned_count'],2);self.assertEqual(report['rejected_records'][0]['provider_company_id'],992)
        deadline=r['deadline'];self.store.change(r['id'],lambda p:p.update(status='failed',stop_reason='SCRIPTED local normalization failure'))
        resumed=self.loop.resume_cached(r['id'],ResumeScoutingRun(continuation_key='explicit-test',reuse_cached_attempts=True));self.assertEqual(resumed['deadline'],deadline)
        with httpx.Client(transport=PaidTransport(self.store,r['id'],'search:0',600000,httpx.MockTransport(handle))) as client:again=client.post('https://api.crustdata.com/company/search',json=body).json()
        self.assertEqual(again,p);self.assertEqual(len(calls),1);self.assertEqual(len(self.store.get(r['id'])['attempts']),1);self.assertEqual(self.store.get(r['id'])['continuations'][0]['prior_status'],'failed')
    def test_full_source_intake_two_company_linked_people_and_grouped_graph(self):
        self.state.reference_material=load_reference_material(APP_ROOT,APP_ROOT/'config/reference-source.json')
        r=self.start();calls=[];graphs=[]
        def handle(request):
            calls.append(request.url.path)
            if request.url.path=='/company/search':return httpx.Response(200,headers={'x-credits-used':'.03'},json={'companies':[{'crustdata_company_id':991,'basic_info':{'name':'SCRIPTED COMPANY','primary_domain':'scripted.example','description':'SCRIPTED TEST: microscopy workflow tool with an attributable source'}}]})
            people=[{'crustdata_person_id':i,'basic_profile':{'name':'SCRIPTED PERSON '+str(i)},'experience':{'employment_details':{'current':[{'employer_crustdata_company_id':991,'title':'Indexed founder role SCRIPTED TEST'}]}}} for i in [1,2]]
            return httpx.Response(200,headers={'x-credits-used':'2'},json=[{'matches':[{'company_data':{'crustdata_company_id':991,'basic_info':{'name':'SCRIPTED COMPANY','primary_domain':'scripted.example','description':'SCRIPTED source description'},'people':{'founders':people,'cxos':people}}}]}])
        source={'url':'https://scripted.example','retrieved_at':'2026-10-24T10:00:00Z','http_status':200,'raw_path':'SCRIPTED_TEST_ONLY','sha256':'a'*64,'excerpt':'SCRIPTED SOFTWARE TEST public company product description, not a real company observation.'}
        def scripted_invoke(transport,packet):
            eid=packet.evidence[0].id;claim={'text':'SCRIPTED SOFTWARE TEST source claim','evidence_ids':[eid]};answer=Answer(summary='SCRIPTED SOFTWARE TEST',evidence_ids=[eid],objections=[],unknowns=['Unknown functional proof'])
            brief=CaseBrief(company_description=claim,research_posture='pursue',main_reason=claim,strongest_facts=[claim],founder_signals=[],founder_unknowns=['Contribution unverified'],decisive_doubt=claim,next_action='Ask a human for attributable work',future_trigger=None,operational_limitations=['SCRIPTED TEST DOUBLE; no actual model call'])
            assessment=SemanticAssessment(findings=[Finding(criterion_id=c.id,result='unknown',evidence_sufficient=False,conflicted=False,evidence_ids=[eid],person_ids=[],rationale='SCRIPTED TEST',comparison_state='mixed',counterevidence_ids=[]) for c in packet.policy.criteria],why_this=answer,why_them=answer,why_now=answer,team_problem_fit=answer,fit='unknown',attractiveness='unknown',actionability='incomplete',proposed_disposition='monitor',investigation=None,interpretation_question=None,next_action='Human research question',stop_or_reopen_condition='Reopen on attributable proof',change_summary='SCRIPTED TEST',case_brief=brief)
            transport.last_metadata={'driver_kind':'SCRIPTED_TEST_DOUBLE','input_tokens':0,'output_tokens':0,'usage_available':True}
            return MatcherResult(outcome='needs_approval',ref=packet.ref,disposition=None,assessment=assessment,investigation=None,missing_required_claims=[],guard_notes=['SCRIPTED TEST DOUBLE'],explanation='SCRIPTED SOFTWARE TEST only',driver_kind='semantic',test_fixture=False,prompt_version='0.3')
        with patch('backend.app.scouting_loop.httpx.HTTPTransport',side_effect=lambda **kw:httpx.MockTransport(handle)),patch.object(self.loop,'_source',return_value=source),patch('backend.app.scouting_loop.ScriptedGraphTransport.invoke',new=scripted_invoke):self.loop._run(r['id'])
        final=self.store.get(r['id'])
        if final['completed_case_ids']:graphs.append(saved_research_graph(self.state,final['completed_case_ids'][0]))
        final=self.store.get(r['id']);self.assertEqual(final['status'],'completed',final);self.assertEqual(calls.count('/company/enrich'),1);self.assertEqual(len(graphs),1)
        self.assertEqual(final['usage']['model_attempts'],1);self.assertEqual(final['usage']['completed_cases'],1);self.assertEqual(final['candidates'][0]['research_state'],'human_research_required')
        context=self.state.load_assessment_context(final['candidates'][0]['case_id']);self.assertEqual(len(context.research_context['people']),2)
        enrich=[e for e in context.evidence if e.source_url=='https://api.crustdata.com/company/enrich'];self.assertEqual(len(enrich),3);self.assertEqual(len({e.retrieved_at for e in enrich}),1)
        grouped=[s for s in graphs[0]['sources'] if s['source_url']=='https://api.crustdata.com/company/enrich'];self.assertEqual(len(grouped),1);self.assertEqual(len(grouped[0]['evidence_ids']),3)

if __name__=='__main__':unittest.main()
