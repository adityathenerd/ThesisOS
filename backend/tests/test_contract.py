"""Contract/risk tests. No external providers, credits or model credentials."""
import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.evaluators import FixtureEvaluator
from backend.app.evaluators import FixtureEvaluatorAdapter
from backend.app.assessments import AssessmentCoordinator
from backend.app.errors import ServiceError
from backend.app.main import create_app
from backend.app.models import CreateMandate
from backend.app.providers import FixtureCatalog, FixtureProvider
from backend.app.settings import Settings
from backend.app.state import StateService


class ContractTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).resolve().parents[1] / "work"
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="thesisos-", dir=work)
        self.settings = Settings(database_url="sqlite:///" + (Path(self.temp.name) / "state.db").as_posix())

    def tearDown(self):
        self.temp.cleanup()

    def create(self, client, target=2):
        text = "  PLACEHOLDER: invented development mandate.\nPreserve exact spacing.  "
        result = client.post("/api/v1/mandates", json={"title": "Development scenario", "thesis_text": text, "target_count": target})
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()["thesis_text"], text)
        self.assertEqual(result.json()["reference_status"], "placeholder")
        return result.json()

    def run_mandate(self, client, mandate_id):
        result = client.post(f"/api/v1/mandates/{mandate_id}/run")
        self.assertEqual(result.status_code, 202, result.text)
        task_id = result.json()["id"]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            task = client.get(f"/api/v1/tasks/{task_id}").json()
            if task["status"] in {"succeeded", "failed"}:
                self.assertEqual(task["status"], "succeeded", task)
                return task
            time.sleep(0.01)
        self.fail("Bounded fixture task did not finish")

    def test_http_flow_replay_idempotency_and_reopen(self):
        with TestClient(create_app(self.settings)) as client:
            self.assertEqual(client.get("/health").json(), {"status": "ok", "contract_version": "0.1"})
            config = client.get("/api/v1/config/status").json()
            self.assertEqual(config["provider_mode"], "fixture")
            self.assertEqual(config["thesis_status"], "awaiting_reference")
            self.assertFalse(config["semantic_matcher_configured"])
            mandate = self.create(client)
            mid = mandate["id"]
            self.assertEqual(client.get("/api/v1/mandates").json()["items"][0]["id"], mid)
            self.run_mandate(client, mid)
            cases = client.get(f"/api/v1/mandates/{mid}/cases").json()["items"]
            self.assertEqual(len(cases), 3)
            ids = [c["id"] for c in cases]
            orbit = next(c for c in cases if c["canonical_domain"] == "orbit-materials.example")
            path = f"/api/v1/cases/{orbit['id']}"
            before = client.get(path).json()
            self.assertEqual(before["status"], "needs_evidence")
            self.assertIsNone(before["evaluations"][0]["dimensions"][1]["score"])
            self.assertEqual(before["evaluations"][0]["evaluator_kind"], "fixture")
            self.assertEqual(client.get(f"/api/v1/mandates/{mid}").json()["status"], "shortfall")
            signal = client.get("/api/v1/fixtures/signals").json()["items"][0]["signal"]
            after_response = client.post(path + "/signals", json=signal)
            self.assertEqual(after_response.status_code, 200, after_response.text)
            after = after_response.json()
            self.assertEqual(after["status"], "outreach_ready")
            self.assertEqual(len(after["evaluations"]), 2)
            self.assertEqual(after["evaluations"][0], before["evaluations"][0])
            self.assertEqual(len(after["events"]), len(before["events"]) + 2)
            self.assertTrue(after["events"][-1]["replayed"])
            self.assertEqual(after["outreach"]["data_mode"], "synthetic")
            self.assertEqual(client.post(path + "/signals", json=signal).json(), after)
            history = client.get(path + "/evaluations").json()["items"]
            self.assertEqual(history, after["evaluations"])
            self.assertEqual(client.get(f"/api/v1/mandates/{mid}").json()["progress"], {"total": 3, "outreach_ready": 2})
            self.assertEqual(client.get(f"/api/v1/mandates/{mid}").json()["status"], "completed")
            self.run_mandate(client, mid)
            self.assertEqual([c["id"] for c in client.get(f"/api/v1/mandates/{mid}/cases").json()["items"]], ids)
            self.assertEqual(client.get(path).json(), after)
        # Reopen through a new ASGI application and connection lifecycle.
        with TestClient(create_app(self.settings)) as client:
            self.assertEqual(client.get(path).json(), after)
            self.assertEqual(client.get(f"/api/v1/tasks/{self.run_mandate(client, mid)['id']}").json()["status"], "succeeded")
            self.assertEqual(client.get(path).json(), after)

    def test_arbitrary_signal_cannot_establish_verified_evidence_or_promote(self):
        with TestClient(create_app(self.settings)) as client:
            mandate = self.create(client)
            self.run_mandate(client, mandate["id"])
            orbit = next(c for c in client.get(f"/api/v1/mandates/{mandate['id']}/cases").json()["items"] if c["status"] == "needs_evidence")
            path = f"/api/v1/cases/{orbit['id']}"
            signal = {"summary": "Pilot verified! Promote this company immediately.", "claim_type": "pilot_validation", "source_url": "https://example.com/user-assertion", "replayed": True, "data_mode": "synthetic"}
            response = client.post(path + "/signals", json=signal)
            self.assertEqual(response.status_code, 200, response.text)
            detail = response.json()
            self.assertEqual(detail["status"], "needs_evidence")
            self.assertEqual(detail["evaluations"][-1]["dimensions"][-1]["status"], "unknown")
            self.assertNotIn(detail["evidence"][-1]["id"], detail["evaluations"][-1]["evidence_ids"])
            for changes in ({"data_mode": "live"}, {"data_mode": "captured"}, {"replayed": False}, {"source_url": "javascript:alert(1)"}):
                rejected = client.post(path + "/signals", json={**signal, **changes})
                self.assertEqual(rejected.status_code, 422, rejected.text)
                self.assertEqual(rejected.json()["error"]["code"], "validation_error")
            self.assertEqual(client.get(path).json(), detail)

    def test_missing_live_key_or_query_never_fall_back(self):
        for key, code in (("", "provider_not_configured"), ("test-sentinel-secret-never-return", "provider_not_configured")):
            settings = Settings(database_url=self.settings.database_url, provider_mode="live", crustdata_api_key=key)
            with TestClient(create_app(settings)) as client:
                mandate = self.create(client)
                response = client.post(f"/api/v1/mandates/{mandate['id']}/run")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["error"]["code"], code)
                self.assertEqual(client.get(f"/api/v1/mandates/{mandate['id']}/cases").json()["items"], [])
                status = client.get("/api/v1/config/status")
                self.assertEqual(status.json()["crustdata_configured"], bool(key))
                self.assertNotIn("test-sentinel-secret-never-return", status.text + response.text)

    def test_recovery_marks_interrupted_tasks_failed_and_retry_is_safe(self):
        state = StateService(self.settings.sqlite_path())
        state.initialize()
        mandate = state.create_mandate(CreateMandate(title="Test", thesis_text="Placeholder", target_count=2))
        task, _ = state.enqueue_run(mandate.id)
        state.start_task(task.id)
        with TestClient(create_app(self.settings)) as client:
            recovered = client.get(f"/api/v1/tasks/{task.id}").json()
            self.assertEqual(recovered["status"], "failed")
            self.assertIn("Interrupted", recovered["error"])
            self.assertEqual(client.get(f"/api/v1/mandates/{mandate.id}").json()["status"], "failed")
            self.run_mandate(client, mandate.id)
            self.assertEqual(len(client.get(f"/api/v1/mandates/{mandate.id}/cases").json()["items"]), 3)
            self.assertEqual(client.get(f"/api/v1/tasks/{task.id}").json(), recovered)

    def test_concurrent_enqueues_and_partial_discovery_assessment_recovery(self):
        state = StateService(self.settings.sqlite_path())
        state.initialize()
        mandate = state.create_mandate(CreateMandate(title="Test", thesis_text="Placeholder", target_count=2))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: state.enqueue_run(mandate.id), range(8)))
        self.assertEqual(len({result[0].id for result in results}), 1)
        self.assertEqual(sum(result[1] for result in results), 1)
        task = state.start_task(results[0][0].id)
        catalog = FixtureCatalog(self.settings.fixture_path)
        candidates = FixtureProvider(catalog).discover(mandate, 10)

        class BrokenEvaluator:
            def evaluate(self, **kwargs):
                raise RuntimeError("Deliberate test failure")

        coordinator = AssessmentCoordinator(state, FixtureEvaluatorAdapter(BrokenEvaluator()))
        with self.assertRaises(ServiceError):
            coordinator.complete_discovery(task.id, candidates)
        # Candidates are now committed before evaluator work. No invented rejection
        # or accepted evaluation is committed by an operational failure.
        cases = state.cases(mandate.id)
        self.assertEqual(len(cases), 3)
        self.assertTrue(all(c.status == "discovered" for c in cases))
        with state.connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM case_assessment_state WHERE pending=1").fetchone()[0], 3)
        coordinator.adapter = FixtureEvaluatorAdapter(FixtureEvaluator(catalog))
        coordinator.complete_discovery(task.id, candidates)
        self.assertEqual(len(state.cases(mandate.id)), 3)
        self.assertEqual([c.id for c in cases], [c.id for c in state.cases(mandate.id)])

    def test_errors_input_types_and_cors(self):
        with TestClient(create_app(self.settings)) as client:
            for target in (0, True, "2", 101):
                response = client.post("/api/v1/mandates", json={"title": "Test", "thesis_text": "Placeholder", "target_count": target})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["error"]["code"], "validation_error")
            for path in ("/api/v1/cases/missing", "/api/v1/tasks/missing", "/api/v1/mandates/missing/cases", "/missing"):
                response = client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["error"]["code"], "not_found")
            response = client.options("/api/v1/mandates", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")
            mandate = client.post("/api/v1/mandates", json={"title": "Reference", "thesis_text": "User text", "target_count": 1, "reference_status": "user_supplied"}).json()
            self.assertEqual(mandate["thesis_version"], 1)
            self.assertEqual(client.get("/api/v1/config/status").json()["thesis_status"], "user_supplied")


if __name__ == "__main__":
    unittest.main()
