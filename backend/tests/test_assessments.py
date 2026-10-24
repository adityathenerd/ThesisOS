"""Detached invocation, conditional acceptance and recovery boundary proofs."""
import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from backend.app.assessments import AssessmentCoordinator, InvestigationSuggestion, PolicyReference, load_reference_material
from backend.app.errors import ServiceError
from backend.app.evaluators import FixtureEvaluator, FixtureEvaluatorAdapter
from backend.app.models import CaseStatus, CreateMandate, Dimension, Evidence, SignalInput
from backend.app.providers import FixtureCatalog, FixtureProvider
from backend.app.settings import APP_ROOT
from backend.app.state import StateService, now, uid


class AssessmentBoundaryTests(unittest.TestCase):
    def setUp(self):
        work = APP_ROOT / "backend" / "work"
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.path = Path(self.temp.name) / "state.db"
        self.state = StateService(self.path)
        self.state.initialize()
        self.catalog = FixtureCatalog(APP_ROOT / "config" / "fixtures.json")
        self.adapter = FixtureEvaluatorAdapter(FixtureEvaluator(self.catalog))
        self.coordinator = AssessmentCoordinator(self.state, self.adapter)
        self.mandate = self.state.create_mandate(CreateMandate(title="LABELED fixture boundary test", thesis_text="PLACEHOLDER, no active policy", target_count=2))
        task, _ = self.state.enqueue_run(self.mandate.id)
        self.task = self.state.start_task(task.id)
        self.candidates = FixtureProvider(self.catalog).discover(self.mandate, 10)
        self.case_ids = self.state.persist_discovery(self.task.id, self.candidates)
        self.orbit = self.case_ids[1]

    def tearDown(self):
        self.temp.cleanup()

    def assess_all(self):
        self.coordinator.complete_discovery(self.task.id, self.candidates)

    def proposal(self, case_id=None):
        context = self.state.load_assessment_context(case_id or self.orbit)
        invocation = self.state.begin_assessment(context)
        return context, self.adapter.evaluate(context, invocation)

    def invocation_status(self, invocation_id):
        with self.state.connection() as db:
            return dict(db.execute("SELECT status,error_code,evaluation_id FROM assessment_invocations WHERE id=?", (invocation_id,)).fetchone())

    def test_blocking_evaluator_releases_read_and_write_transactions(self):
        entered, release = threading.Event(), threading.Event()
        base = self.adapter

        class BlockingAdapter:
            def evaluate(self, context, invocation_id):
                entered.set()
                if not release.wait(5):
                    raise AssertionError("Test did not release evaluator")
                return base.evaluate(context, invocation_id)

        coordinator = AssessmentCoordinator(self.state, BlockingAdapter())
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(coordinator.assess_case, self.orbit)
            try:
                self.assertTrue(entered.wait(3))
                other = self.state.mandate(self.mandate.id).model_copy(update={"id": "lock-probe-mandate"})
                # Immediate write with a short lock timeout must succeed while
                # the fake evaluator remains blocked.
                with closing(sqlite3.connect(self.path, timeout=0.2)) as db:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute("INSERT INTO mandates VALUES (?,?)", (other.id, other.model_dump_json()))
                    db.commit()
                # WAL permits writers alongside readers; successful TRUNCATE
                # also proves the snapshot read transaction is not retained.
                with closing(sqlite3.connect(self.path, timeout=0.2)) as db:
                    self.assertEqual(db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0], 0)
                self.assertFalse(future.done())
            finally:
                release.set()
            self.assertEqual(future.result(timeout=3).recommendation, "needs_evidence")

    def test_signal_arriving_during_blocked_evaluator_invalidates_its_acceptance(self):
        self.assess_all()
        entered, release = threading.Event(), threading.Event()
        base = self.adapter

        class BlockingAdapter:
            def evaluate(self, context, invocation_id):
                entered.set()
                if not release.wait(5):
                    raise AssertionError("Test did not release evaluator")
                return base.evaluate(context, invocation_id)

        coordinator = AssessmentCoordinator(self.state, BlockingAdapter())
        signal = SignalInput.model_validate(self.catalog.companies["orbit"]["signals"][0]["input"])
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(coordinator.assess_case, self.orbit)
            try:
                self.assertTrue(entered.wait(3))
                self.assertTrue(self.state.ingest_replay(self.orbit, signal, self.catalog))
                newer = self.state.detail(self.orbit)
            finally:
                release.set()
            with self.assertRaises(ServiceError) as raised:
                future.result(timeout=3)
            self.assertEqual(raised.exception.code, "stale_version")
        current = self.state.detail(self.orbit)
        self.assertEqual(current.evaluations, newer.evaluations)
        self.assertEqual(current.status, newer.status)
        self.assertEqual(current.version, newer.version)
        self.assertEqual(current.events[-1].event_type, "assessment_failed")
        after = self.coordinator.replay_signal(self.orbit, signal, self.catalog)
        self.assertEqual(after.status, "outreach_ready")
        self.assertEqual(len(after.evaluations), 2)

    def test_case_thesis_policy_company_and_evidence_revisions_reject_stale_inputs(self):
        self.assess_all()
        for revision in ("case", "thesis_content", "thesis_version", "policy", "company", "evidence_content", "evidence_added"):
            with self.subTest(revision=revision):
                context, proposal = self.proposal()
                with self.state.connection(write=True) as db:
                    if revision == "case":
                        case = self.state._read(db, "cases", type(context.case), self.orbit)
                        case.version += 1
                        case.next_action = "Newer accepted operational revision"
                        db.execute("UPDATE cases SET payload=? WHERE id=?", (case.model_dump_json(), case.id))
                    elif revision.startswith("thesis"):
                        mandate = self.state._read(db, "mandates", type(context.mandate), self.mandate.id)
                        if revision == "thesis_content":
                            mandate.thesis_text += " changed without version increment"
                        else:
                            mandate.thesis_version += 1
                        self.state._put_mandate(db, mandate)
                    elif revision == "policy":
                        policy = PolicyReference(reference="test-only-draft-not-activated", version=1, status="draft")
                        db.execute("INSERT OR REPLACE INTO mandate_policy_refs VALUES (?,?)", (self.mandate.id, policy.model_dump_json()))
                    elif revision == "company":
                        row = db.execute("SELECT payload FROM companies WHERE id=?", (context.company.id,)).fetchone()
                        payload = json.loads(row[0])
                        payload["company_name"] += " revised"
                        db.execute("UPDATE companies SET payload=? WHERE id=?", (json.dumps(payload), context.company.id))
                    elif revision == "evidence_content":
                        evidence = context.evidence[0].model_copy(update={"summary": "Revised observation under same ID: digest must catch it"})
                        db.execute("UPDATE evidence SET payload=? WHERE id=?", (evidence.model_dump_json(), evidence.id))
                    else:
                        evidence = Evidence(id=uid("evidence"), company_id=context.company.id, claim_type="test_observation", summary="Additional synthetic observation", retrieved_at=now(), source_key=uid("test-source"), data_mode="synthetic")
                        db.execute("INSERT INTO evidence VALUES (?,?,?,?)", (evidence.id, evidence.company_id, evidence.source_key, evidence.model_dump_json()))
                        db.execute("INSERT INTO case_evidence VALUES (?,?)", (self.orbit, evidence.id))
                current_detail = self.state.detail(self.orbit)
                current_mandate = self.state.mandate(self.mandate.id)
                with self.assertRaises(ServiceError) as raised:
                    self.state.accept_assessment(proposal)
                self.assertEqual(raised.exception.code, "stale_version")
                self.assertEqual(self.state.detail(self.orbit), current_detail)
                self.assertEqual(self.state.mandate(self.mandate.id), current_mandate)
                self.assertEqual(self.invocation_status(proposal.invocation_id)["status"], "stale")

    def test_evidence_injection_in_findings_result_and_investigation_is_rejected(self):
        self.assess_all()
        # First foreign ID belongs to another company. Second belongs to this
        # company but is NOT linked to the assessed case or supplied manifest.
        foreign = self.state.detail(self.case_ids[0]).evidence[0].id
        detached = Evidence(id=uid("evidence"), company_id=self.state.detail(self.orbit).company_id, claim_type="unlinked", summary="Not supplied to this case", source_key=uid("unlinked-source"), retrieved_at=now(), data_mode="synthetic")
        with self.state.connection(write=True) as db:
            db.execute("INSERT INTO evidence VALUES (?,?,?,?)", (detached.id, detached.company_id, detached.source_key, detached.model_dump_json()))
        for foreign_id in (foreign, detached.id):
            for field in ("finding", "overall", "investigation"):
                with self.subTest(foreign_id=foreign_id, field=field):
                    context, proposal = self.proposal()
                    result = proposal.result
                    if field == "finding":
                        result = result.model_copy(update={"dimensions": [*result.dimensions, Dimension(name="Injected", status="unknown", rationale="Must not be accepted", evidence_ids=[foreign_id])]})
                    elif field == "overall":
                        result = result.model_copy(update={"evidence_ids": [*result.evidence_ids, foreign_id]})
                    else:
                        result = result.model_copy(update={"investigation": InvestigationSuggestion(case_id=self.orbit, decision_question="Test-only question", missing_claim="Test-only claim", evidence_ids=(foreign_id,))})
                    proposal = proposal.model_copy(update={"result": result})
                    before, mandate = self.state.detail(self.orbit), self.state.mandate(self.mandate.id)
                    with self.assertRaises(ServiceError) as raised:
                        self.state.accept_assessment(proposal)
                    self.assertEqual(raised.exception.code, "invalid_evidence")
                    self.assertEqual(self.state.detail(self.orbit), before)
                    self.assertEqual(self.state.mandate(self.mandate.id), mandate)
                    self.assertEqual(self.invocation_status(proposal.invocation_id)["status"], "invalid")

    def test_newer_acceptance_wins_and_exact_acceptance_retry_is_idempotent(self):
        _, old = self.proposal()
        _, newer = self.proposal()
        accepted = self.state.accept_assessment(newer)
        self.assertNotEqual(accepted.id, newer.invocation_id)
        self.assertNotEqual(accepted.id, newer.snapshot_id)
        detail = self.state.detail(self.orbit)
        self.assertEqual(self.state.accept_assessment(newer), accepted)
        self.assertEqual(self.state.detail(self.orbit), detail)
        with self.assertRaises(ServiceError) as raised:
            self.state.accept_assessment(old)
        self.assertEqual(raised.exception.code, "stale_version")
        self.assertEqual(self.state.detail(self.orbit), detail)

    def test_forged_evidence_payload_cannot_override_stored_company_ownership(self):
        other = self.state.detail(self.case_ids[0]).evidence[0]
        target_company = self.state.detail(self.orbit).company_id
        forged = other.model_copy(update={"company_id": target_company})
        with self.state.connection(write=True) as db:
            db.execute("UPDATE evidence SET payload=? WHERE id=?", (forged.model_dump_json(), other.id))
            db.execute("INSERT INTO case_evidence VALUES (?,?)", (self.orbit, other.id))
        with self.assertRaises(ServiceError) as raised:
            self.state.load_assessment_context(self.orbit)
        self.assertEqual(raised.exception.code, "invalid_evidence")

    def test_semantic_proposal_is_not_activated_by_a_policy_reference(self):
        with self.state.connection(write=True) as db:
            db.execute("INSERT INTO mandate_policy_refs VALUES (?,?)", (self.mandate.id, PolicyReference(reference="isolated-test-draft", version=1, status="draft").model_dump_json()))
        _, proposal = self.proposal()
        result = proposal.result.model_copy(update={"evaluator_kind": "semantic"})
        with self.assertRaises(ServiceError) as raised:
            self.state.accept_assessment(proposal.model_copy(update={"result": result}))
        self.assertEqual(raised.exception.code, "invalid_transition")
        self.assertEqual(self.state.detail(self.orbit).evaluations, [])

    def test_failed_replay_keeps_observation_and_can_retry_without_duplicate_signal(self):
        self.assess_all()
        before = self.state.detail(self.orbit)
        signal = self.catalog.companies["orbit"]["signals"][0]["input"]
        from backend.app.models import SignalInput
        signal = SignalInput.model_validate(signal)

        class BrokenAdapter:
            def evaluate(self, context, invocation_id):
                raise RuntimeError("secret-sentinel-provider-payload")

        self.coordinator.adapter = BrokenAdapter()
        with self.assertRaises(ServiceError) as raised:
            self.coordinator.replay_signal(self.orbit, signal, self.catalog)
        self.assertEqual(raised.exception.code, "evaluator_unavailable")
        failed = self.state.detail(self.orbit)
        self.assertEqual(failed.status, before.status)
        self.assertEqual(failed.evaluations, before.evaluations)
        self.assertEqual(len(failed.evidence), len(before.evidence) + 1)
        self.assertEqual(failed.events[-1].event_type, "assessment_failed")
        self.assertNotIn("secret-sentinel", failed.model_dump_json())
        self.coordinator.adapter = self.adapter
        after = self.coordinator.replay_signal(self.orbit, signal, self.catalog)
        self.assertEqual(after.status, "outreach_ready")
        self.assertEqual(len(after.evidence), len(failed.evidence))
        self.assertEqual(sum(e.event_type == "signal_replayed" for e in after.events), 1)
        self.assertEqual(len(after.evaluations), 2)
        self.assertEqual(self.coordinator.replay_signal(self.orbit, signal, self.catalog), after)

    def test_new_observation_can_leave_required_claim_unresolved(self):
        self.assess_all()
        base = self.adapter

        class HoldAdapter:
            def evaluate(self, context, invocation_id):
                proposal = base.evaluate(context, invocation_id)
                result = proposal.result.model_copy(update={
                    "recommendation": CaseStatus.needs_evidence, "outreach": None,
                    "missing_claims": ["Verified founding-team role (test-only required claim)"],
                    "dimensions": [*proposal.result.dimensions, Dimension(name="Required team claim — labeled test double", status="unknown", rationale="A new company observation does not resolve the missing team claim.", evidence_ids=[])],
                    "reasoning_summary": "LABELED TEST DOUBLE, not executed semantic reasoning: required team claim remains unresolved.",
                })
                return proposal.model_copy(update={"result": result})

        self.coordinator.adapter = HoldAdapter()
        from backend.app.models import SignalInput
        signal = SignalInput.model_validate(self.catalog.companies["orbit"]["signals"][0]["input"])
        after = self.coordinator.replay_signal(self.orbit, signal, self.catalog)
        self.assertEqual(after.status, "needs_evidence")
        self.assertIn("test-only required claim", after.evaluations[-1].missing_claims[0])
        self.assertIsNone(after.outreach)
        self.assertEqual(self.state.mandate(self.mandate.id).progress.outreach_ready, 1)

    def test_interrupted_partial_batch_resumes_only_pending_cases(self):
        first = self.coordinator.assess_case(self.case_ids[0], task_id=self.task.id)
        context = self.state.load_assessment_context(self.orbit)
        interrupted = self.state.begin_assessment(context, task_id=self.task.id)
        reopened = StateService(self.path)
        reopened.initialize()
        self.assertEqual(reopened.recover_interrupted_tasks(), 1)
        self.assertEqual(reopened.task(self.task.id).status, "failed")
        self.assertEqual(self.invocation_status(interrupted)["status"], "failed")
        self.assertEqual(reopened.detail(self.case_ids[0]).evaluations[0].id, first.id)
        retry, _ = reopened.enqueue_run(self.mandate.id)
        reopened.start_task(retry.id)
        AssessmentCoordinator(reopened, self.adapter).complete_discovery(retry.id, self.candidates)
        self.assertEqual(reopened.task(retry.id).status, "succeeded")
        for case_id in self.case_ids:
            self.assertEqual(len(reopened.detail(case_id).evaluations), 1)
        self.assertEqual(reopened.mandate(self.mandate.id).progress.total, 3)
        self.assertEqual(reopened.recover_interrupted_tasks(), 0)

    def test_schema_one_migration_preserves_history_and_context_is_explicitly_unavailable(self):
        self.assess_all()
        before = self.state.detail(self.orbit)
        with self.state.connection() as db:
            db.executescript("DROP TABLE assessment_invocations; DROP TABLE case_assessment_state; DROP TABLE mandate_policy_refs; PRAGMA user_version=1;")
        self.state.initialize()
        self.assertEqual(self.state.detail(self.orbit), before)
        context = self.state.load_assessment_context(self.orbit)
        self.assertEqual(context.versions.policy.status, "unavailable")
        self.assertEqual(context.people.status, "unavailable")
        self.assertEqual(context.relationships.status, "unavailable")
        self.assertEqual(context.market.status, "unavailable")
        self.assertEqual(context.prior_evaluation, before.evaluations[-1])
        self.assertEqual(context.current_gaps, tuple(before.evaluations[-1].missing_claims))
        self.assertFalse(hasattr(context, "fixture_key"))
        retry, _ = self.state.enqueue_run(self.mandate.id)
        self.state.start_task(retry.id)
        self.coordinator.complete_discovery(retry.id, self.candidates)
        self.assertEqual(self.state.detail(self.orbit), before)

    def test_source_reference_is_pinned_versioned_and_never_activates_policy(self):
        reference = load_reference_material(APP_ROOT, APP_ROOT / "config" / "reference-source.json")
        self.state.reference_material = reference
        context, proposal = self.proposal()
        self.assertEqual(context.reference_material.document_version, "0.3")
        self.assertEqual(context.reference_material.review_status, "human_reviewed_direction_only")
        self.assertFalse(context.reference_material.policy_active)
        self.assertIn('"therapeutics": "core"', context.reference_material.outline_text)
        self.assertEqual(context.versions.policy.status, "unavailable")
        self.assertEqual(self.state.mandate(self.mandate.id).thesis_text, "PLACEHOLDER, no active policy")
        # Explicit reference reload/revision invalidates an in-flight proposal.
        self.state.reference_material = reference.model_copy(update={"document_version": "test-only-revision"})
        with self.assertRaises(ServiceError) as raised:
            self.state.accept_assessment(proposal)
        self.assertEqual(raised.exception.code, "stale_version")


if __name__ == "__main__":
    unittest.main()
