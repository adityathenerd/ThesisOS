"""Optional actual-socket smoke test against an isolated fixture server.

Usage: python backend/tests/http_smoke.py http://127.0.0.1:8001
Creates one clearly labeled placeholder mandate in the chosen server's DB.
"""
import json
import sys
import time

import httpx


def main(base_url):
    with httpx.Client(base_url=base_url, timeout=10) as client:
        assert client.get("/health").json()["status"] == "ok"
        config = client.get("/api/v1/config/status").json()
        assert config["provider_mode"] == "fixture"
        response = client.post("/api/v1/mandates", json={"title": "HTTP smoke — synthetic placeholder", "thesis_text": "PLACEHOLDER: actual reference pending; socket-level verification only.", "target_count": 2, "reference_status": "placeholder"})
        assert response.status_code == 201, response.text
        mid = response.json()["id"]

        def run():
            queued = client.post(f"/api/v1/mandates/{mid}/run")
            assert queued.status_code == 202, queued.text
            task_id = queued.json()["id"]
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                task = client.get(f"/api/v1/tasks/{task_id}").json()
                if task["status"] in {"succeeded", "failed"}:
                    assert task["status"] == "succeeded", task
                    return task_id
                time.sleep(0.05)
            raise AssertionError("Task exceeded smoke test deadline")

        run()
        cases = client.get(f"/api/v1/mandates/{mid}/cases").json()["items"]
        assert len(cases) == 3
        assert client.get(f"/api/v1/mandates/{mid}").json()["status"] == "shortfall"
        orbit = next(c for c in cases if c["canonical_domain"] == "orbit-materials.example")
        path = f"/api/v1/cases/{orbit['id']}"
        before = client.get(path).json()
        signal = client.get("/api/v1/fixtures/signals").json()["items"][0]["signal"]
        after_response = client.post(path + "/signals", json=signal)
        assert after_response.status_code == 200, after_response.text
        after = after_response.json()
        assert after["status"] == "outreach_ready"
        assert len(after["evaluations"]) == 2
        assert after["evaluations"][0] == before["evaluations"][0]
        assert client.get(f"/api/v1/mandates/{mid}").json()["status"] == "completed"
        assert client.post(path + "/signals", json=signal).json() == after
        run()
        assert [c["id"] for c in client.get(f"/api/v1/mandates/{mid}/cases").json()["items"]] == [c["id"] for c in cases]
        assert client.get(path).json() == after
        assert client.post(path + "/signals", json={**signal, "data_mode": "live"}).status_code == 422
        print(json.dumps({"result": "PASS", "transport": "actual HTTP socket", "base_url": base_url, "cases": 3, "outreach_ready_after_replay": 2, "evaluations_before": 1, "evaluations_after": 2, "rerun_case_ids_stable": True, "catalog_replay_idempotent": True, "live_browser_signal_rejected": True}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001")
