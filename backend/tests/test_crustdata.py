"""Documented Crustdata adapter tests. MockTransport prevents paid calls."""
import json
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend.app.errors import ServiceError
from backend.app.main import create_app
from backend.app.models import CreateMandate, Mandate
from backend.app.providers import CrustdataSearchProvider
from backend.app.settings import APP_ROOT, Settings


class CrustdataTests(unittest.TestCase):
    def setUp(self):
        work = APP_ROOT / "backend" / "work"
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.settings = Settings(database_url="sqlite:///" + (Path(self.temp.name) / "state.db").as_posix(), provider_mode="live", crustdata_api_key="test-sentinel-secret", crustdata_search_config=APP_ROOT / "config" / "crustdata-search.example.json")

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def mandate():
        return Mandate(**CreateMandate(title="Placeholder", thesis_text="No thesis relevance is inferred", target_count=1).model_dump(), id="mandate-test", created_at="2026-10-24T05:27:00Z", updated_at="2026-10-24T05:27:00Z")

    def test_empty_optional_domain_preserves_entire_paid_result_and_raw_receipt(self):
        raw={'companies':[{'crustdata_company_id':8,'basic_info':{'name':'Missing domain','primary_domain':''}},{'crustdata_company_id':9,'basic_info':{'name':'Known domain','primary_domain':'known.example'}}]}
        saved=[]
        provider=CrustdataSearchProvider(self.settings,httpx.MockTransport(lambda request:httpx.Response(200,json=raw,headers={'x-request-id':'test-request','x-credits-used':'0.06'})),saved.append)
        candidates=provider.execute_request({'search':{'query':'test','mode':'semantic'},'fields':['basic_info.name','basic_info.primary_domain'],'limit':8})
        self.assertEqual(len(candidates),2);self.assertIsNone(candidates[0].canonical_domain)
        self.assertEqual(candidates[0].provider_company_id,'8')
        self.assertEqual(json.loads(saved[0]['response_text']),raw)
        self.assertEqual(saved[0]['diagnostic']['credits_used'],'0.06')

    def test_response_saved_before_invalid_required_identity_and_can_replay_offline(self):
        raw={'companies':[{'basic_info':{'name':'Unresolved','primary_domain':None}}]};saved=[]
        provider=CrustdataSearchProvider(self.settings,httpx.MockTransport(lambda request:httpx.Response(200,json=raw)),saved.append)
        with self.assertRaises(ServiceError) as caught:
            provider.execute_request({'search':{'query':'test','mode':'semantic'},'fields':['basic_info.name','basic_info.primary_domain'],'limit':8})
        self.assertIn('Missing stable company identity',caught.exception.message)
        self.assertEqual(json.loads(saved[0]['response_text']),raw)

    def test_documented_request_mapping_and_live_http_persistence_without_semantic_claims(self):
        calls = []

        def handle(request):
            self.assertEqual(str(request.url), "https://api.crustdata.com/company/search")
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.headers["authorization"], "Bearer test-sentinel-secret")
            self.assertEqual(request.headers["x-api-version"], "2025-11-01")
            body = json.loads(request.content)
            self.assertEqual(body["limit"], 1)
            self.assertEqual(body["fields"], ["basic_info.name", "basic_info.primary_domain", "headcount.total"])
            self.assertEqual(body["filters"]["conditions"][0], {"field": "headcount.growth_percent.6m", "type": ">", "value": 15})
            calls.append(body)
            # Explicit mock identity: no fabricated actual provider company ID.
            return httpx.Response(200, json={"companies": [{"crustdata_company_id": "mock-identity", "basic_info": {"name": "Mock real-data company", "primary_domain": "mock-company.example"}, "headcount": {"total": 579}}], "next_cursor": "not-followed", "total_count": 5730})

        provider = CrustdataSearchProvider(self.settings, httpx.MockTransport(handle))
        with patch("backend.app.main.build_provider", return_value=provider):
            with TestClient(create_app(self.settings)) as client:
                cfg = client.get("/api/v1/config/status")
                self.assertTrue(cfg.json()["crustdata_configured"])
                self.assertEqual(cfg.json()["discovery_query_status"], "unapproved_or_access_test_configuration")
                self.assertNotIn("test-sentinel-secret", cfg.text)
                mandate = client.post("/api/v1/mandates", json={"title": "Mock integration", "thesis_text": "PLACEHOLDER", "target_count": 1}).json()
                mid = mandate["id"]

                def run():
                    response = client.post(f"/api/v1/mandates/{mid}/run")
                    self.assertEqual(response.status_code, 202, response.text)
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        task = client.get(f"/api/v1/tasks/{response.json()['id']}").json()
                        if task["status"] in {"succeeded", "failed"}:
                            self.assertEqual(task["status"], "succeeded", task)
                            return
                        time.sleep(0.01)
                    self.fail("Task timed out")

                run()
                self.assertEqual(len(calls), 1)
                cases = client.get(f"/api/v1/mandates/{mid}/cases").json()["items"]
                self.assertEqual(len(cases), 1)
                self.assertEqual(cases[0]["data_mode"], "live")
                self.assertEqual(cases[0]["status"], "needs_evidence")
                path = f"/api/v1/cases/{cases[0]['id']}"
                detail = client.get(path).json()
                self.assertTrue(all(e["data_mode"] == "live" for e in detail["evidence"]))
                self.assertTrue(all(e["observed_at"] is None for e in detail["evidence"]))
                self.assertEqual(detail["events"][0]["data_mode"], "live")
                self.assertEqual(detail["evaluations"][0]["evaluator_kind"], "fixture")
                self.assertEqual(detail["evaluations"][0]["data_mode"], "synthetic")
                self.assertIsNone(detail["thesis_fit"])
                self.assertIsNone(detail["evidence_sufficiency"])
                self.assertIsNone(detail["outreach"])
                run()
                self.assertEqual(len(calls), 2)  # Explicit rerun, no automatic retry/pagination.
                refreshed=client.get(path).json()
                self.assertEqual(refreshed['id'],detail['id'])
                self.assertEqual(refreshed['evaluations'][0],detail['evaluations'][0])
                self.assertEqual(len(refreshed['evaluations']),2)
                replay = {"summary": "Invented browser claim", "claim_type": "pilot_validation", "source_url": None, "replayed": True, "data_mode": "synthetic"}
                updated = client.post(path + "/signals", json=replay)
                self.assertEqual(updated.status_code, 200, updated.text)
                self.assertEqual(updated.json()["data_mode"], "live")
                self.assertEqual(updated.json()["evidence"][-1]["data_mode"], "synthetic")
                self.assertEqual(updated.json()["status"], "needs_evidence")
                self.assertIsNone(updated.json()["outreach"])
                self.assertEqual(client.get(f"/api/v1/mandates/{mid}").json()["status"], "shortfall")

    def test_provider_errors_are_sanitized_and_never_retried(self):
        scenarios = [(401, {"error": "test-sentinel-secret"}, "provider_not_configured"), (429, {"error": "test-sentinel-secret"}, "provider_unavailable"), (500, {"error": "test-sentinel-secret"}, "provider_unavailable"), (200, {"unexpected": "test-sentinel-secret"}, "provider_unavailable"), (200, {"companies": [{"broken": True}]}, "provider_unavailable")]
        for status, payload, code in scenarios:
            calls = []

            def handle(request):
                calls.append(request)
                return httpx.Response(status, json=payload)

            provider = CrustdataSearchProvider(self.settings, httpx.MockTransport(handle))
            with self.assertRaises(ServiceError) as raised:
                provider.discover(self.mandate(), 1)
            self.assertEqual(raised.exception.code, code)
            self.assertNotIn("test-sentinel-secret", raised.exception.message)
            self.assertEqual(len(calls), 1)

        provider = CrustdataSearchProvider(self.settings, httpx.MockTransport(lambda request: httpx.Response(200, json={"companies": [{"basic_info": {"name": "Bad domain", "primary_domain": "username@company.example"}}]})))
        with self.assertRaises(ServiceError):
            provider.discover(self.mandate(), 1)

    def test_live_query_opt_in_and_missing_key_fail_before_network(self):
        def forbidden(request):
            self.fail("Missing configuration must not make any network request")

        for settings in (replace(self.settings, crustdata_search_config=None), replace(self.settings, crustdata_api_key="")):
            with self.assertRaises(ServiceError) as raised:
                CrustdataSearchProvider(settings, httpx.MockTransport(forbidden)).discover(self.mandate(), 1)
            self.assertEqual(raised.exception.code, "provider_not_configured")

    def test_ranked_transport_optional_description_missing_headcount_and_null_total(self):
        for description in (None, 'Provider description is a claim, not product proof'):
            def handle(request):
                payload=json.loads(request.content)
                self.assertIn('search',payload);self.assertNotIn('filters',payload)
                return httpx.Response(200,json={'companies':[{'crustdata_company_id':321,'basic_info':{'name':'Mock','primary_domain':'mock.example','description':description}}],'total_count':None,'next_cursor':None})
            provider=CrustdataSearchProvider(self.settings,httpx.MockTransport(handle))
            candidates=provider.execute_request({'search':{'query':'Referral intake for clinics','mode':'hybrid'},'fields':['basic_info.name','basic_info.primary_domain','basic_info.description'],'limit':1})
            self.assertEqual(candidates[0].description,description)
            self.assertEqual(candidates[0].provider_company_id,'321')


if __name__ == "__main__":
    unittest.main()
