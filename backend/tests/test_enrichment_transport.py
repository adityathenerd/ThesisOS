import json,tempfile,unittest
from pathlib import Path
import httpx
from backend.app.enrichment_transport import EnrichmentTransport
from backend.app.errors import ServiceError
from backend.app.settings import APP_ROOT,Settings


class EnrichmentTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=APP_ROOT/'backend/work');self.folder=Path(self.temp.name)
        p={'payload':{'endpoints':[{'path':'/company/enrich','status':'enabled','base_credits':2,'fields':{'enabled':['basic_info','people'],'disabled':['social_posts']}}]}}
        (self.folder/'account-permissions.json').write_text(json.dumps(p));self.calls=[]
        (self.folder/'scope.json').write_text(json.dumps({'case_ids':['test-case'],'collection_closed':False}))
        self.body={'crustdata_company_ids':[1],'fields':['basic_info','people']}
    def tearDown(self):self.temp.cleanup()
    def client(self,handler):return EnrichmentTransport(Settings(crustdata_api_key='software-test-only'),self.folder,transport=httpx.MockTransport(handler))
    def test_raw_response_survives_parse_error_and_reuses_exact_intent(self):
        def respond(r):self.calls.append(r);return httpx.Response(200,text='{unparsed',headers={'x-credits-used':'2'})
        c=self.client(respond);a=c.call('test','/company/enrich',self.body,case_id='test-case');b=c.call('test','/company/enrich',self.body,case_id='test-case')
        self.assertEqual(a,b);self.assertEqual(a['response_text'],'{unparsed');self.assertEqual(len(self.calls),1);self.assertEqual(c.export()['actual_or_conservative_reserved_credits'],2)
        with self.assertRaises(ServiceError):c.call('test','/company/enrich',{**self.body,'crustdata_company_ids':[2]},case_id='test-case')
    def test_disabled_field_and_shared_budget_block_before_network(self):
        def forbidden(r):raise AssertionError('No request authorized')
        c=self.client(forbidden)
        with self.assertRaises(ServiceError):c.call('disabled','/company/enrich',{**self.body,'fields':['social_posts']},case_id='test-case')
        with c.db() as db:db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?)',('prior','/person/enrich',149_000_000,149_000_000,'received','test',0,'{}'))
        with self.assertRaises(ServiceError):c.call('over','/company/enrich',self.body,case_id='test-case')
        with c.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],1)
    def test_transport_failure_does_not_retry_and_reservation_is_retained(self):
        def fail(r):self.calls.append(r);raise httpx.ConnectError('Software test',request=r)
        c=self.client(fail);a=c.call('failed','/company/enrich',self.body,case_id='test-case');self.assertIsNone(a['http_status']);c.call('failed','/company/enrich',self.body,case_id='test-case')
        self.assertEqual(len(self.calls),1);self.assertEqual(c.export()['actual_or_conservative_reserved_credits'],2)


if __name__=='__main__':unittest.main()
