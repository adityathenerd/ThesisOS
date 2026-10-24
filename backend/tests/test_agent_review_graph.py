import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient
from agents.models import Answer, Finding, MatcherResult, SemanticAssessment,Investigation
import httpx
from agents.research_graph import ResearchGraph

from backend.app.agent_bridge import AgentAssessmentStore, GateProof, ReviewEligibility, ScriptedGraphTransport, comparison_packet, run_scripted_comparison
from backend.app.assessments import load_reference_material
from backend.app.errors import ServiceError
from backend.app.main import create_app
from backend.app.models import CreateMandate, SignalInput
from backend.app.providers import FixtureCatalog, FixtureProvider
from backend.app.research_graph import saved_research_graph
from backend.app.settings import APP_ROOT, Settings
from backend.app.state import StateService
from backend.app.batch import BatchStore
from agents.brief import to_case_brief
from agents.models import CaseBrief
from backend.app.research_ingest import accept_research
from backend.app.follow_up import research_follow_up,save_current_question_binding,execute_research_intent


class AgentReviewGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=APP_ROOT/'backend/work')
        self.path=Path(self.temp.name)/'state.db'
        reference=load_reference_material(APP_ROOT,APP_ROOT/'config/reference-source.json')
        self.state=StateService(self.path,reference);self.state.initialize()
        self.mandate=self.state.create_mandate(CreateMandate(title='SCRIPTED REVIEW SOFTWARE TEST',thesis_text='Not a real approved qualification policy',target_count=1))
        self.catalog=FixtureCatalog(APP_ROOT/'config/fixtures.json')
        task,_=self.state.enqueue_run(self.mandate.id);self.state.start_task(task.id)
        cases=self.state.persist_discovery(task.id,FixtureProvider(self.catalog).discover(self.mandate,3))
        self.case_id=cases[1]
        self.state.fail_task(task.id,'Deliberately detached software-test setup; no provider calls')

    def tearDown(self):self.temp.cleanup()

    def findings(self,packet,qualify=False):
        eid=packet.evidence[0].id
        answer=Answer(summary='SCRIPTED SOFTWARE TEST: known source versus unresolved proof',evidence_ids=[eid],objections=[],unknowns=[])
        return SemanticAssessment(findings=[Finding(criterion_id=c.id,result='meets' if qualify else 'unknown',evidence_sufficient=qualify,conflicted=False,evidence_ids=[eid],person_ids=[],rationale='SCRIPTED SOFTWARE TEST; not semantic proof',comparison_state='supported' if qualify else 'mixed',counterevidence_ids=[]) for c in packet.policy.criteria],why_this=answer,why_them=answer,why_now=answer,team_problem_fit=answer,fit='passes' if qualify else 'unknown',attractiveness='unknown',actionability='incomplete',proposed_disposition='qualify' if qualify else 'monitor',investigation=None,interpretation_question=None,next_action='Wait for explicit human review; no model qualification',stop_or_reopen_condition='Reopen on changed attributable proof',change_summary='Scripted test only')

    def stored_recommendation(self,*,unknown_gate=False):
        context=self.state.load_assessment_context(self.case_id)
        packet=comparison_packet(context,output_tokens=1000)
        result=MatcherResult(outcome='assessment',ref=packet.ref,disposition='qualify',assessment=self.findings(packet,True),investigation=None,missing_required_claims=[],guard_notes=['SCRIPTED REVIEW TEST DOUBLE'],explanation='Only an isolated fake recommendation; human approval required',driver_kind='scripted',test_fixture=True,evidence_modes=['synthetic'],criterion_evidence_sufficient={c.id:True for c in packet.policy.criteria},requires_human_qualification_review=True)
        names=['product_or_experimental_proof','problem_program','attributed_founder_contribution','differentiated_approach','contradictions_reviewed']
        gates=[GateProof(name=n,status='unknown' if unknown_gate and n=='product_or_experimental_proof' else 'met',evidence_ids=[packet.evidence[0].id]) for n in names]
        eligibility=ReviewEligibility(scope='synthetic_software_test',track='H',gates=gates,specialist_review='not_applicable',unresolved_required_claims=[])
        inv=self.state.begin_assessment(context)
        return AgentAssessmentStore(self.state).record(context,inv,packet,result,eligibility=eligibility,provenance='scripted_review_test_double')

    def client(self):return TestClient(create_app(Settings(database_url='sqlite:///'+self.path.as_posix())))

    def test_actual_compiled_scripted_graph_runs_detached_and_comparison_cannot_qualify(self):
        context=self.state.load_assessment_context(self.case_id)
        packet=comparison_packet(context,output_tokens=1000)
        before=self.state.detail(self.case_id)
        entered,release=threading.Event(),threading.Event()
        actual=ScriptedGraphTransport()
        class BlockingActualTransport:
            def invoke(inner,ctx,scripted):
                entered.set()
                if not release.wait(5):raise RuntimeError('Test release missing')
                return actual.invoke(ctx,scripted)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(run_scripted_comparison,self.state,self.case_id,self.findings(packet).model_dump(mode='json'),transport=BlockingActualTransport())
            try:
                self.assertTrue(entered.wait(3))
                self.state.create_mandate(CreateMandate(title='Concurrent writer during actual graph boundary',thesis_text='Placeholder',target_count=1))
            finally:release.set()
            assessment=future.result(timeout=20)
        after=self.state.detail(self.case_id)
        self.assertEqual(after.version,before.version);self.assertEqual(after.status,before.status)
        self.assertEqual(after.evaluations,[])
        self.assertEqual(after.agent_assessments[0].outcome,'needs_approval')
        self.assertEqual(after.agent_assessments[0].structured_result['assessment']['findings'][0]['comparison_state'],'mixed')
        self.assertFalse(after.agent_assessments[0].eligible_for_human_review)
        self.assertIsNone(actual.last_metadata['model'])
        with self.client() as client:
            response=client.post(f'/api/v1/cases/{self.case_id}/qualification-review',json={'assessment_id':assessment,'expected_case_version':after.version,'decision':'approve'})
            self.assertEqual(response.status_code,409,response.text)
            self.assertEqual(response.json()['error']['code'],'ineligible_qualification')

    def test_human_review_is_explicit_idempotent_and_never_outreach_ready(self):
        assessment=self.stored_recommendation()
        initial=self.state.detail(self.case_id)
        self.assertNotEqual(initial.status,'qualified');self.assertEqual(initial.evaluations,[])
        request={'assessment_id':assessment,'expected_case_version':initial.version,'decision':'approve','note':'Explicit synthetic software-test human action'}
        with self.client() as client:
            path=f'/api/v1/cases/{self.case_id}/qualification-review'
            response=client.post(path,json=request)
            self.assertEqual(response.status_code,200,response.text)
            detail=response.json();self.assertEqual(detail['status'],'qualified');self.assertIsNone(detail['outreach'])
            self.assertTrue(detail['qualification_reviews'][0]['current']);self.assertTrue(detail['qualification_reviews'][0]['synthetic_test'])
            self.assertIsNone(detail['qualification_reviews'][0]['reviewer_identity'])
            self.assertEqual(client.post(path,json=request).json(),detail)
            self.assertEqual(self.state.mandate(self.mandate.id).progress.outreach_ready,0)
        reopened=StateService(self.path,self.state.reference_material);reopened.initialize()
        self.assertEqual(len(reopened.detail(self.case_id).qualification_reviews),1)
        signal=SignalInput.model_validate(self.catalog.companies['orbit']['signals'][0]['input'])
        self.state.ingest_replay(self.case_id,signal,self.catalog)
        changed=self.state.detail(self.case_id)
        self.assertEqual(changed.status,'needs_evidence');self.assertFalse(changed.qualification_reviews[0].current)
        with self.client() as client:
            response=client.post(path,json=request)
            self.assertEqual(response.status_code,409)
            self.assertEqual(response.json()['error']['code'],'stale_version')

    def test_unknown_gate_rejected_and_request_evidence_recorded(self):
        assessment=self.stored_recommendation(unknown_gate=True)
        version=self.state.detail(self.case_id).version
        request={'assessment_id':assessment,'expected_case_version':version,'decision':'approve'}
        with self.client() as client:
            path=f'/api/v1/cases/{self.case_id}/qualification-review'
            self.assertEqual(client.post(path,json=request).status_code,409)
            response=client.post(path,json={**request,'decision':'request_evidence','note':'Need an inspectable artifact'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['status'],'needs_evidence')
            self.assertEqual(response.json()['qualification_reviews'][0]['decision'],'request_evidence')

    def test_mismatched_agent_reference_and_injected_citations_refused(self):
        context=self.state.load_assessment_context(self.case_id);packet=comparison_packet(context,output_tokens=1000)
        result=MatcherResult(outcome='needs_approval',ref=packet.ref,disposition=None,assessment=self.findings(packet),investigation=None,missing_required_claims=[],guard_notes=[],explanation='Scripted comparison',driver_kind='scripted',test_fixture=True)
        invocation=self.state.begin_assessment(context)
        for malformed in (result.model_copy(update={'ref':packet.ref.model_copy(update={'case_version':999})}),result.model_copy(update={'assessment':result.assessment.model_copy(update={'why_this':result.assessment.why_this.model_copy(update={'evidence_ids':['foreign-evidence']})})})):
            with self.assertRaises(ServiceError):AgentAssessmentStore(self.state).record(context,invocation,packet,malformed)
        self.assertEqual(self.state.detail(self.case_id).agent_assessments,[])

    def test_graph_schema_export_cache_and_append_only_snapshots(self):
        first=ResearchGraph.model_validate(saved_research_graph(self.state,self.case_id))
        self.assertEqual(first.case_id,self.case_id);self.assertIsNone(first.research_example_ref)
        self.assertTrue(first.open_questions);self.assertFalse(any(n.kind=='person' for n in first.nodes))
        self.assertEqual(saved_research_graph(self.state,self.case_id),first.model_dump(mode='json'))
        signal=SignalInput.model_validate(self.catalog.companies['orbit']['signals'][0]['input'])
        self.state.ingest_replay(self.case_id,signal,self.catalog)
        second=ResearchGraph.model_validate(saved_research_graph(self.state,self.case_id))
        self.assertNotEqual(first.graph_id,second.graph_id)
        with self.state.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM research_graph_snapshots').fetchone()[0],2)
        with self.client() as client:
            response=client.get(f'/api/v1/cases/{self.case_id}/research-graph')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['schema_version'],'0.1')

    def test_brief_is_exact_idempotent_saved_projection_and_marks_stale_inputs(self):
        context=self.state.load_assessment_context(self.case_id);packet=comparison_packet(context,output_tokens=1000);eid=packet.evidence[0].id
        claim={'text':'SCRIPTED SOFTWARE TEST sourced claim','evidence_ids':[eid]}
        brief=CaseBrief(company_description=claim,research_posture='pursue',main_reason=claim,strongest_facts=[claim],founder_signals=[],founder_unknowns=['No named person supplied'],decisive_doubt=claim,next_action='Inspect attributed work',future_trigger=None,operational_limitations=['Scripted test; no model call'])
        assessment=self.findings(packet).model_copy(update={'case_brief':brief})
        result=MatcherResult(outcome='needs_approval',ref=packet.ref,disposition=None,assessment=assessment,investigation=None,missing_required_claims=[],guard_notes=[],explanation='Scripted projection software test',driver_kind='scripted',test_fixture=True)
        invocation=self.state.begin_assessment(context);aid=AgentAssessmentStore(self.state).record(context,invocation,packet,result,provenance='scripted_test')
        projection=to_case_brief(result,assessment_ref=aid).model_dump(mode='json');store=BatchStore(self.state)
        store.save_brief(self.case_id,aid,projection);store.save_brief(self.case_id,aid,projection)
        self.assertEqual(store.brief(self.case_id)['status'],'ready')
        with self.state.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM case_briefs').fetchone()[0],1)
        altered=json.loads(json.dumps(projection));altered['brief']['main_reason']['text']='Unsaved replacement conclusion'
        with self.assertRaises(ServiceError):store.save_brief(self.case_id,aid,altered)
        self.state.ingest_replay(self.case_id,SignalInput.model_validate(self.catalog.companies['orbit']['signals'][0]['input']),self.catalog)
        self.assertEqual(store.brief(self.case_id)['status'],'stale')
        with self.assertRaises(ServiceError):store.save_brief(self.case_id,aid,projection)

    def followup_fixture(self,*,executable=False):
        case=self.state.detail(self.case_id);url='https://example.com/research-source'
        history=[] if executable else [{'task_id':'actual-report-attempt','question_id':'historical-question','status':'inaccessible','summary':'Selected report source returned an access failure','accepted_evidence_ids':[],'source_urls':[url]},{'task_id':'unrelated-profile-attempt','question_id':'other-historical-question','status':'succeeded','summary':'A profile was retrieved; no experimental question answered','accepted_evidence_ids':[],'source_urls':['https://example.com/profile']}]
        follow={'pass_id':'SCRIPTED FOLLOWUP TEST','attempts':history,'attempt_details':[{'task_id':a['task_id'],'question_id':a['question_id'],'summary':a['summary']} for a in history],'remaining_calls':1 if executable else 0,'capabilities':[{'action':'public.web.fetch','subject_kinds':['company'],'purpose':'investigation'}] if executable else [],'allowed_public_urls':[url]}
        accept_research(self.state,self.case_id,[],{'follow_up':follow},expected_case_version=case.version)
        context=self.state.load_assessment_context(self.case_id);packet=comparison_packet(context,output_tokens=1000);eid=packet.evidence[0].id
        claim={'text':'SCRIPTED TEST known source and unresolved question','evidence_ids':[eid]}
        brief=CaseBrief(company_description=claim,research_posture='pursue',main_reason=claim,strongest_facts=[claim],founder_signals=[],founder_unknowns=['Unknown contributor'],decisive_doubt=claim,next_action='Obtain a sourced experimental report',future_trigger=None,operational_limitations=['Scripted isolated test'])
        inv=Investigation(criterion_id='C4',subject_kind='company',subject_id=packet.company_id,action='public.web.fetch',query=url,question='Can the specified source be retrieved?',decision_consequence='Resolve this bounded evidence question before further pursuit',max_calls=1) if executable else None
        assessment=self.findings(packet).model_copy(update={'case_brief':brief,'investigation':inv})
        result=MatcherResult(outcome='needs_approval',ref=packet.ref,disposition=None,assessment=assessment,investigation=None,missing_required_claims=[],guard_notes=[],explanation='SCRIPTED FOLLOWUP TEST',driver_kind='scripted',test_fixture=True)
        invocation=self.state.begin_assessment(context);aid=AgentAssessmentStore(self.state).record(context,invocation,packet,result,provenance='scripted_test')
        return context,packet,result,aid,inv

    def test_current_question_keeps_only_verified_matching_attempts(self):
        context,packet,result,aid,_=self.followup_fixture();eid=packet.evidence[0].id
        point={'id':'stable-report-question','criterion_ids':['C4'],'question':'Can the full report be supplied?','decision_consequence':'Inspect the actual experiment before another pursuit decision','what_to_obtain':'An authorized full report','evidence_ids':[eid],'investigation':None}
        save_current_question_binding(self.state,self.case_id,aid,[point],[{'task_id':'actual-report-attempt','question_id':point['id'],'why_relevant':'Actual attempted source was the requested report, not a person lookup'}])
        flow=research_follow_up(self.state,self.case_id);q=flow['workflow']['human_research_points'][0]
        self.assertEqual(flow['workflow']['state'],'human_research_required');self.assertEqual(q['attempted_task_ids'],['actual-report-attempt']);self.assertNotIn('unrelated-profile-attempt',q['attempted_task_ids'])
        detail=next(d for d in flow['attempt_details'] if d['task_id']=='actual-report-attempt')
        self.assertEqual(detail['question_id'],point['id']);self.assertEqual(detail['historical_question_id'],'historical-question')
        self.state.ingest_replay(self.case_id,SignalInput.model_validate(self.catalog.companies['orbit']['signals'][0]['input']),self.catalog)
        self.assertEqual(research_follow_up(self.state,self.case_id)['workflow']['state'],'reassessment_required')

    def test_explicit_executor_is_version_bound_not_a_scheduler_and_does_not_invent_resolution(self):
        context,packet,result,aid,inv=self.followup_fixture(executable=True)
        flow=research_follow_up(self.state,self.case_id);self.assertEqual(flow['workflow']['state'],'research_required');intent=flow['workflow']['task_intents'][0];calls=[]
        def retrieve(request):
            calls.append(request)
            # Network executes after the reservation transaction has closed.
            with self.state.connection(write=True) as db:db.execute('SELECT 1')
            self.assertEqual(research_follow_up(self.state,self.case_id)['workflow']['state'],'actively_researching')
            return httpx.Response(200,text='<h1>Public source, interpretation still required</h1>')
        request={'assessment_id':aid,'expected_case_version':context.case.version,'idempotency_key':intent['idempotency_key']}
        first=execute_research_intent(self.state,self.case_id,request,transport=httpx.MockTransport(retrieve));second=execute_research_intent(self.state,self.case_id,request,transport=httpx.MockTransport(retrieve))
        self.assertEqual(first,second);self.assertEqual(len(calls),1);self.assertEqual(self.state.detail(self.case_id).version,context.case.version)
        after=research_follow_up(self.state,self.case_id);self.assertEqual(after['workflow']['state'],'human_research_required');self.assertEqual(after['workflow']['human_research_points'][0]['attempted_task_ids'],[first['attempt']['task_id']]);self.assertFalse(after['qualification_accepted'])

    def test_cached_paid_result_acceptance_keeps_interrupted_receipt_and_refuses_changed_inputs(self):
        context,packet,result,aid,_=self.followup_fixture()
        context=self.state.load_assessment_context(self.case_id)
        interrupted=self.state.begin_assessment(context);self.state.record_assessment_failure(interrupted,'assessment_interrupted','Simulated startup race; no paid call')
        with self.assertRaises(ServiceError):AgentAssessmentStore(self.state).record(context,interrupted,packet,result)
        context=self.state.load_assessment_context(self.case_id)
        recovery=self.state.begin_assessment(context);newid=AgentAssessmentStore(self.state).record(context,recovery,packet,result,provenance='cached_output_acceptance_software_test')
        with self.state.connection() as db:self.assertEqual(db.execute('SELECT status FROM assessment_invocations WHERE id=?',(interrupted,)).fetchone()[0],'failed')
        self.assertNotEqual(aid,newid)
        self.state.ingest_replay(self.case_id,SignalInput.model_validate(self.catalog.companies['orbit']['signals'][0]['input']),self.catalog)
        changed=self.state.load_assessment_context(self.case_id);invocation=self.state.begin_assessment(changed)
        with self.assertRaises(ServiceError):AgentAssessmentStore(self.state).record(changed,invocation,packet,result)


if __name__=='__main__':unittest.main()
