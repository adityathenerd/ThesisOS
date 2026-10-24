# Continuous scouting: submission build

User authorization: 24 October 2026. Build a continuous scouting loop, run it for up to 30 minutes, create a GitHub repository under adityathenerd and commit/push working checkpoints. This supersedes the earlier conditional request that depended on an existing harness.

## Now

Backend owns one durable run with start/status/stop, a persisted UTC deadline, bounded sequential work and resumable inspection. Agent owner supplies the existing discovery-to-evidence-to-assessment/graph worker seam. Frontend exposes actual progress and stopping. Root owns repository setup, credential/capture exclusion, commits/pushes and integrated verification.

Initial live limits: at most 30 minutes, four new company cases, 20 paid Crustdata requests, 50 credits and four model assessments; one active worker. Reuse the reviewed four-track health/biosciences reference and source-backed query rules. Deduplicate existing identities. A new run cannot consume or reopen the closed enrichment batch's budget. No automatic paid retries. Stop before starting work beyond deadline/caps, on explicit stop, authentication failure or an unbudgeted operation. In-flight network calls need finite timeouts and must report their actual outcome.

No invented evidence or completed-state claims, automatic qualification or outreach. Every new case must retain source provenance and expose incomplete work honestly. Human approval remains necessary for qualification. Preserve all existing case evidence, assessments, graphs and readiness decisions. Existing-case pre-outreach calibration continues separately against saved evidence without provider/model calls.

## Next

Verify the first functional slice with isolated fixtures and stop/deadline/deduplication/budget tests, then start one live run while UI polish continues. Commit and push verified checkpoints to a private repository. Record exact limits, timestamps, actual requests and outcomes. A cap or exhausted candidate list may legitimately stop the run before 30 minutes.

## Later

Cross-process scheduling, unattended restarts, broad crawling, automatic query expansion and general production hardening are outside this submission build.
