import hashlib,json
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import unittest
from backend.tests import test_agent_review_graph as fixtures
from backend.app.bounded_followthrough import FollowThroughStage,StartFollowThrough
from backend.app.scouting_loop import RunStore,LoopStopped
from backend.app.settings import APP_ROOT,Settings
from backend.app.research_graph import saved_research_graph

class NoDispatch:
    def submit(self,*args):raise AssertionError('No worker/model dispatch in this software test')

class BoundedFollowThroughTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.AgentReviewGraphTests(methodName='runTest');self.fixture.setUp();self.state=self.fixture.state
        self.context,self.packet,self.result,self.aid,_=self.fixture.followup_fixture();self.parent='SCRIPTED_PARENT_'+Path(self.fixture.temp.name).name
        self.folder=APP_ROOT/'backend/work/scouting-runs'/self.parent;self.folder.mkdir(parents=True,exist_ok=True)
        raw=self.folder/'cached.json';raw.write_text(json.dumps({'received_at':'2026-10-24T10:00:00Z','response_text':json.dumps([{'matches':[{'company_data':{'crustdata_company_id':991,'people':{'founders':[{'crustdata_person_id':1,'basic_profile':{'name':'SCRIPTED PERSON'},'experience':{'employment_details':{'current':[{'employer_company_id':['other'],'employee_title':'OTHER'},{'employer_company_id':['991'],'employee_title':'SCRIPTED actual-company role'}]}}}],'cxos':[]}}}]}])}))
        page=self.folder/'home.html';page.write_text('<a href="/product">Product</a><a href="/about">About</a>')
        self.candidate={'key':'991','case_id':self.context.case.id,'company_name':self.context.case.company_name,'domain':self.context.case.canonical_domain,'stage':'complete','assessment_id':self.aid,'source_receipt':{'raw_path':str(page.relative_to(APP_ROOT))}}
        parent={'id':self.parent,'status':'stopped','mandate_id':self.context.mandate.id,'deadline':(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat(),'attempts':[{'intent':'enrich:991','kind':'provider','status':'received','quoted_microcredits':2000000,'actual_microcredits':2000000,'raw_path':str(raw.relative_to(APP_ROOT))}],'candidates':[self.candidate],'completed_case_ids':[self.context.case.id]}
        with self.state.connection(write=True) as db:db.execute('INSERT INTO scouting_runs VALUES (?,?,?,?,?,?)',(self.parent,self.parent,'stopped',json.dumps(parent),'TEST','TEST'))
        self.worker=FollowThroughStage(self.state,Settings(),NoDispatch());self.stage=self.worker.start_stage(self.parent,StartFollowThrough(execute_live=True,idempotency_key=self.parent+':child'),submit=False)
    def tearDown(self):self.fixture.tearDown()
    def test_cached_roles_and_two_directed_sources_batched_before_one_reassessment(self):
        parent=RunStore(self.state).get(self.parent);calls=[];seen=[]
        def source(stage,candidate,url):
            calls.append(url);return {'url':url,'retrieved_at':'2026-10-24T11:00:00Z','sha256':hashlib.sha256(url.encode()).hexdigest(),'excerpt':'SCRIPTED new attributed source text; no functional validation','raw_path':'SCRIPTED'}
        def assess(stage,key,case):
            context=self.state.load_assessment_context(case);seen.append(context);saved_research_graph(self.state,case)
        with patch.object(self.worker,'_source',side_effect=source),patch.object(self.worker,'_assess',side_effect=assess):self.worker._case(self.stage['id'],parent,self.candidate)
        self.assertEqual(len(calls),2);self.assertEqual(len(seen),1);self.assertEqual(len(seen[0].research_context['people']),1);self.assertEqual(seen[0].case.version,self.context.case.version+1)
        current=self.worker.store.get(self.stage['id']);self.assertEqual(current['usage']['provider_requests'],0);self.assertEqual(len(current['attempts']),2)
        with self.state.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM semantic_assessments WHERE case_id=?',(self.context.case.id,)).fetchone()[0],1)
    def test_stopped_child_blocks_further_paid_intake_without_restart(self):
        self.worker.store.change(self.stage['id'],lambda p:p.update(status='failed',stop_reason='SCRIPTED provider/model failure'))
        with self.assertRaises(LoopStopped):self.worker.process_intake_case(self.parent,self.context.case.id)
        self.assertEqual(self.worker.store.get(self.stage['id'])['status'],'failed')
    def test_external_actual_tool_packet_consumes_two_pages_without_duplicate_fetch(self):
        folder=self.folder/'external-followthrough';folder.mkdir();proof=folder/'SCRIPTED.txt';proof.write_text('SCRIPTED observed tool output fixture')
        packet={'case_id':self.context.case.id,'domain':self.candidate['domain'],'new_public_page_visits':2,'source_url':'https://'+self.candidate['domain']+'/tool','observed_at':'2026-10-24T11:00:00Z','observations':['SCRIPTED bounded tool observation, not product validation'],'limitations':['SCRIPTED software test fixture'],'proof_files':{'accessibility':str(proof)},'proof_sha256':{'accessibility':hashlib.sha256(proof.read_bytes()).hexdigest()}}
        (folder/(self.candidate['domain']+'.json')).write_text(json.dumps(packet));seen=[]
        with patch.object(self.worker,'_source',side_effect=AssertionError('Must not duplicate external browser work')),patch.object(self.worker,'_assess',side_effect=lambda *args:seen.append(saved_research_graph(self.state,self.context.case.id))):self.worker._case(self.stage['id'],RunStore(self.state).get(self.parent),self.candidate)
        self.assertEqual(len(seen),1);attempts=self.worker.store.get(self.stage['id'])['attempts'];self.assertEqual(attempts[0]['request']['public_page_attempts'],2)

if __name__=='__main__':unittest.main()


