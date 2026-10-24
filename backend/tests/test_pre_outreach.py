import copy,hashlib,json
from pathlib import Path
import unittest
from backend.tests import test_agent_review_graph as fixtures
from backend.app.pre_outreach import active_sources,accept_review,pre_outreach_review
from backend.app.research_ingest import accept_research
from backend.app.agent_bridge import AgentAssessmentStore,comparison_packet
from backend.app.errors import ServiceError
from agents.pre_outreach import PreOutreachOverlay,PreOutreachGuidance,build_pre_outreach_review

class PreOutreachPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.AgentReviewGraphTests(methodName='runTest');self.fixture.setUp();self.state=self.fixture.state
        self.context,self.packet,self.result,self.aid,_=self.fixture.followup_fixture();self.case_id=self.context.case.id
        folder=Path(self.fixture.temp.name);policy=folder/'policy.md';guidance=folder/'guidance.json';policy.write_text('SCRIPTED POLICY ONLY');guidance.write_text('SCRIPTED GUIDANCE ONLY')
        self.registry=folder/'registry.json';self.sources={'active':True,'policy_overlay':{'id':'SCRIPTED','path':str(policy),'sha256':hashlib.sha256(policy.read_bytes()).hexdigest(),'version':'0.1'},'case_guidance':{'path':str(guidance),'sha256':hashlib.sha256(guidance.read_bytes()).hexdigest(),'version':'0.1'}};self.registry.write_text(json.dumps(self.sources));self.sources=active_sources(self.registry)
        eid=self.packet.evidence[0].id;claim={'text':'SCRIPTED source-supported introductory topic','evidence_ids':[eid]};condition={**claim,'status':'supported'}
        overlay=PreOutreachOverlay(id='SCRIPTED',source_path=str(policy),source_sha256=self.sources['policy_overlay']['sha256'],base_reference_sha256=self.context.reference_material.document_sha256,authorization_ref='SCRIPTED TEST AUTHORIZATION')
        normalized=PreOutreachGuidance(source_path=str(guidance),source_sha256=self.sources['case_guidance']['sha256'],version='0.1',entry_id='SCRIPTED',input_ref=self.packet.ref,assessment_ref=self.aid,author='SCRIPTED TEST',suggested_category='outreach_candidate',rationale=claim,minimum={k:condition for k in ['identity_and_scope','concrete_product_program_or_problem','useful_conversation_reason']},call_questions=[claim],relevant_person={'status':'unknown','explanation':'SCRIPTED unknown person'},contact_route={'status':'not_established','explanation':'SCRIPTED route unverified'})
        self.review=build_pre_outreach_review(self.packet,self.result,assessment_ref=self.aid,overlay=overlay,guidance=normalized).model_dump(mode='json')
    def tearDown(self):self.fixture.tearDown()
    def save(self,review=None):return accept_review(self.state,self.context,self.aid,review or self.review,sources=self.sources,registry_path=self.registry)
    def get(self):return pre_outreach_review(self.state,self.case_id,registry_path=self.registry)
    def test_current_immutable_idempotent_and_no_case_or_model_mutation(self):
        before=self.state.detail(self.case_id).model_dump(mode='json');first=self.save();self.assertEqual(first,self.save());self.assertEqual(self.get()['status'],'ready');self.assertEqual(self.state.detail(self.case_id).model_dump(mode='json'),before)
        with self.state.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM pre_outreach_reviews').fetchone()[0],1)
        changed=copy.deepcopy(self.review);changed['rationale']['text']='A different interpretation'
        with self.assertRaises(ServiceError):self.save(changed)
    def test_case_change_marks_saved_projection_stale_and_rejects_old_acceptance(self):
        self.save();accept_research(self.state,self.case_id,[],{'limitations':['SCRIPTED changed research input']},expected_case_version=self.context.case.version)
        self.assertEqual(self.get()['status'],'stale')
        with self.assertRaises(ServiceError):self.save()
    def test_overlay_bytes_change_blocks_current_claim(self):
        self.save();Path(self.sources['policy_overlay']['path']).write_text('CHANGED SCRIPTED POLICY')
        self.assertEqual(self.get()['status'],'stale')
        with self.assertRaises(ServiceError):self.save()
    def test_guidance_bytes_change_blocks_current_claim(self):
        self.save();Path(self.sources['case_guidance']['path']).write_text('CHANGED SCRIPTED GUIDANCE')
        self.assertEqual(self.get()['status'],'stale')
    def test_new_assessment_on_same_case_marks_old_review_stale(self):
        self.save();current=self.state.load_assessment_context(self.case_id);packet=comparison_packet(current,output_tokens=1000);invocation=self.state.begin_assessment(current)
        newer=AgentAssessmentStore(self.state).record(current,invocation,packet,self.result,provenance='SCRIPTED TEST')
        self.assertNotEqual(newer,self.aid);self.assertIn('current_assessment_changed',self.get()['stale_reasons'])
    def test_foreign_citation_and_wrong_guidance_pin_rejected(self):
        for field in ['foreign','wrong_pin']:
            bad=copy.deepcopy(self.review)
            if field=='foreign':bad['rationale']['evidence_ids']=['foreign-evidence']
            else:bad['guidance_source_sha256']='b'*64
            with self.assertRaises(ServiceError):self.save(bad)
        self.assertEqual(self.get()['status'],'unavailable')
    def test_unavailable_http_is_read_only_and_does_not_invent_review(self):
        with self.fixture.client() as client:r=client.get('/api/v1/cases/'+self.case_id+'/pre-outreach-review')
        self.assertEqual(r.status_code,200);self.assertEqual(r.json()['status'],'unavailable');self.assertIsNone(r.json()['review'])
        with self.state.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM pre_outreach_reviews').fetchone()[0],0)

if __name__=='__main__':unittest.main()
