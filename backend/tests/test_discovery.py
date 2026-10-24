import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend.app.assessments import load_reference_material
from backend.app.discovery import ApprovedCompanySearchProvider, CompanyCatalog, DiscoveryApproval, DiscoveryBranchInput, DiscoveryStore, MappedPredicate, compile_discovery
from backend.app.errors import ServiceError
from backend.app.main import create_app
from backend.app.models import CreateMandate
from backend.app.settings import APP_ROOT, Settings
from backend.app.state import StateService
from backend.app.batch import BatchStore
from backend.app.providers import Candidate


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=APP_ROOT/'backend/work')
        self.reference = load_reference_material(APP_ROOT, APP_ROOT/'config/reference-source.json')
        self.path = Path(self.temp.name)/'state.db'
        self.state = StateService(self.path, self.reference)
        self.state.initialize()
        self.mandate = self.state.create_mandate(CreateMandate(title='TEST ONLY branch', thesis_text='Unapproved normalization; reviewed direction is separate', target_count=1))
        self.catalog = CompanyCatalog.model_validate_json((APP_ROOT/'config/provider-catalog/company-search.json').read_text())
        draft = json.loads((APP_ROOT/'config/discovery-branches.proposed.json').read_text())['branches'][0]
        self.branch = DiscoveryBranchInput.model_validate({**draft, 'mandate_id':self.mandate.id})
        self.compiled = compile_discovery(self.branch, self.catalog, self.reference)
        self.store = DiscoveryStore(self.state)

    def tearDown(self):
        self.temp.cleanup()

    def test_batch_replaying_saved_pool_does_not_consume_encounter_limit(self):
        store=BatchStore(self.state);batch=store.create('TEST bounded batch')
        store.update(batch['id'],limits={**batch['limits'],'retained_pool_encounters':1})
        candidate=Candidate(key='123',company_name='TEST ONLY',canonical_domain='batch.example',evidence=[],provider_company_id='123')
        store.record_pool(batch['id'],self.branch,[candidate]);store.record_pool(batch['id'],self.branch,[candidate])
        self.assertEqual(store.get(batch['id'])['progress']['encounters'],1)
        self.assertEqual(store.get(batch['id'])['progress']['unique_pool'],1)
        with self.assertRaises(ServiceError):store.record_pool(batch['id'],self.branch,[candidate,Candidate(key='456',company_name='TEST second',canonical_domain='second.example',evidence=[],provider_company_id='456')])

    def approve(self, compiled=None, **changes):
        c=compiled or self.compiled
        approval=DiscoveryApproval(id='test-review',mandate_id=self.mandate.id,branch_digest=c.branch_digest,request_digest=c.request_digest,catalog_digest=c.catalog_digest,scope='discovery_only',approved=True,reviewer='explicit test operator',lossy_filters_reviewed=False,max_calls=1,max_result_slots=1,max_quoted_microcredits=c.quoted_microcredits_ceiling)
        approval=approval.model_copy(update=changes)
        self.store.register(c,approval,self.catalog)
        return approval

    def task(self):
        task,_=self.state.enqueue_run(self.mandate.id)
        return self.state.start_task(task.id)

    def test_verified_compile_without_qualification_approval_and_proxy_review(self):
        self.assertNotIn('filters',self.compiled.request)
        self.assertIn('referral intake',self.compiled.request['search']['query'])
        self.approve()
        with self.state.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM mandate_policy_refs').fetchone()[0],0)
        for draft in json.loads((APP_ROOT/'config/discovery-branches.proposed.json').read_text())['branches']:
            compile_discovery(DiscoveryBranchInput.model_validate(draft),self.catalog,self.reference)
        predicate=MappedPredicate(criterion_id='C1',field='taxonomy.categories',operator='in',value=['Therapeutics','Biotechnology'],semantic_mapping='proxy',explanation='Taxonomy is a lossy scope proxy, not experimental evidence')
        proxy=compile_discovery(self.branch.model_copy(update={'predicates':[predicate]}),self.catalog,self.reference)
        with self.assertRaises(ServiceError):
            self.approve(proxy,id='proxy-no-review')
        self.approve(proxy,id='proxy-reviewed',lossy_filters_reviewed=True)

    def test_unknown_fields_values_operators_and_empty_search_refused(self):
        for changes in ({'field':'basic_info.description'},{'operator':'contains'},{'value':['Imaginary YC Quality Sector']}):
            p={'criterion_id':'C1','field':'taxonomy.categories','operator':'in','value':['Biotechnology'],'semantic_mapping':'proxy','explanation':'Test proxy'}
            with self.assertRaises(ServiceError):
                compile_discovery(self.branch.model_copy(update={'predicates':[MappedPredicate(**{**p,**changes})]}),self.catalog,self.reference)
        with self.assertRaises(ServiceError):
            compile_discovery(self.branch.model_copy(update={'ranked':None}),self.catalog,self.reference)
        generic=self.branch.ranked.model_copy(update={'query':'all companies'})
        with self.assertRaises(ServiceError):
            compile_discovery(self.branch.model_copy(update={'ranked':generic}),self.catalog,self.reference)

    def test_atomic_dedup_reservation_and_failed_usage_not_zeroed(self):
        approval=self.approve();task=self.task()
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes=list(pool.map(lambda _:self.store.reserve(approval.id,self.catalog,task_id=task.id),range(8)))
        self.assertEqual(sum(created for _,created in outcomes),1)
        self.assertEqual(len({r['id'] for r,_ in outcomes}),1)
        self.store.finish(outcomes[0][0]['id'],error='Safe mock failure; billing unknown')
        with self.assertRaises(ServiceError) as raised:
            self.store.reserve(approval.id,self.catalog,task_id=task.id,attempt_key='deliberate-retry')
        self.assertEqual(raised.exception.code,'resource_limit')
        self.state.reference_material=self.reference.model_copy(update={'document_version':'changed-reference'})
        with self.assertRaises(ServiceError):
            self.store.reserve(approval.id,self.catalog,task_id=task.id)

    def test_reviewed_http_flow_provenance_coverage_and_no_repeat_network(self):
        approval=self.approve()
        selection=Path(self.temp.name)/'selection.json'
        selection.write_text(json.dumps({'approval_id':approval.id,'attempt_key':'initial'}))
        settings=Settings(database_url='sqlite:///'+self.path.as_posix(),provider_mode='live',crustdata_api_key='sentinel-test-key',crustdata_search_config=selection)
        calls=[]
        def handle(request):
            body=json.loads(request.content);calls.append(body)
            self.assertNotIn('headcount.total',body['fields'])
            self.assertNotIn('filters',body)
            self.assertIn('clinic administrators',body['search']['query'])
            return httpx.Response(200,json={'companies':[{'crustdata_company_id':'mock-company','basic_info':{'name':'TEST ONLY scope lead','primary_domain':'scope-lead.example'},'headcount':None}],'total_count':100,'next_cursor':'not-followed'})
        provider=ApprovedCompanySearchProvider(settings,self.state,transport=httpx.MockTransport(handle))
        with patch('backend.app.main.build_provider',return_value=provider):
            with TestClient(create_app(settings)) as client:
                def run():
                    response=client.post(f'/api/v1/mandates/{self.mandate.id}/run')
                    self.assertEqual(response.status_code,202,response.text)
                    for _ in range(100):
                        task=client.get('/api/v1/tasks/'+response.json()['id']).json()
                        if task['status'] in {'succeeded','failed'}:
                            self.assertEqual(task['status'],'succeeded',task);return
                        time.sleep(.02)
                    self.fail('Task did not complete')
                run()
                case=client.get(f'/api/v1/mandates/{self.mandate.id}/cases').json()['items'][0]
                before=client.get('/api/v1/cases/'+case['id']).json()
                self.assertEqual(case['status'],'needs_evidence')
                self.assertTrue(all(':branch:' in e['source_key'] for e in before['evidence']))
                run()
                self.assertEqual(len(calls),1)
                self.assertEqual(client.get('/api/v1/cases/'+case['id']).json(),before)
                coverage=client.get(f'/api/v1/mandates/{self.mandate.id}/discovery').json()
                self.assertEqual(coverage['tracks']['H']['attempts'],1)
                self.assertEqual(coverage['tracks']['T']['coverage'],'not_executed')
                self.assertIn('unknown',coverage['novelty'])
                with self.state.connection() as db:
                    refs=json.loads(db.execute('SELECT payload FROM evidence_discovery_refs').fetchone()[0])
                    self.assertEqual(refs['reference_version'],'0.3')
                    self.assertFalse(refs['qualification_policy_active'])
        # Default fixture service must not append a synthetic funnel to a
        # mandate that already contains genuine provider research.
        with TestClient(create_app(Settings(database_url='sqlite:///'+self.path.as_posix()))) as client:
            response=client.post(f'/api/v1/mandates/{self.mandate.id}/run')
            self.assertEqual(response.status_code,409,response.text)
            self.assertEqual(response.json()['error']['code'],'invalid_transition')
            self.assertEqual(len(client.get(f'/api/v1/mandates/{self.mandate.id}/cases').json()['items']),1)

    def test_production_route_rejects_access_test_config_and_interruption_retains_reservation(self):
        settings=Settings(database_url='sqlite:///'+self.path.as_posix(),provider_mode='live',crustdata_api_key='sentinel',crustdata_search_config=APP_ROOT/'config/crustdata-search.example.json')
        with TestClient(create_app(settings)) as client:
            response=client.post(f'/api/v1/mandates/{self.mandate.id}/run')
            self.assertEqual(response.status_code,503)
            self.assertIn('access-test',response.json()['error']['message'])
        approval=self.approve();task=self.task()
        execution,_=self.store.reserve(approval.id,self.catalog,task_id=task.id)
        reopened=StateService(self.path,self.reference);reopened.initialize();reopened.recover_interrupted_tasks()
        with reopened.connection() as db:
            row=db.execute('SELECT status,result_count,quoted_microcredits FROM discovery_executions WHERE id=?',(execution['id'],)).fetchone()
        self.assertEqual(row[0],'interrupted');self.assertIsNone(row[1]);self.assertGreater(row[2],0)


if __name__=='__main__': unittest.main()
