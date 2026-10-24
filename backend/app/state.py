"""Authoritative transactional state. JSON projections retain the v0.1 wire shapes.

SQLite uniqueness owns company/case identity; evaluations/events are append-only.
Changing databases requires replacing this service, not transport or evaluation.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .errors import ServiceError
from .models import Case, CaseDetail, CreateMandate, Evaluation, Evidence, Event, Mandate, OutreachPackage, Progress, SignalInput, Task
from .assessments import AssessmentContext, AssessmentProposal, CompanyContext, EvidenceManifestEntry, InputVersions, PolicyReference, UnavailableContext, content_version


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class StateService:
    def __init__(self, path: Path, reference_material=None):
        self.path = path
        self.reference_material = reference_material

    @contextmanager
    def connection(self, write=False, snapshot=False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            elif snapshot:
                db.execute("BEGIN")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in {0, 1, 2, 3, 4}:
                raise ValueError("Database schema is newer than this harness supports")
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS mandates (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS companies (
                    id TEXT PRIMARY KEY, source_key TEXT NOT NULL UNIQUE,
                    canonical_domain TEXT UNIQUE, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY, mandate_id TEXT NOT NULL REFERENCES mandates(id),
                    company_id TEXT NOT NULL REFERENCES companies(id), fixture_key TEXT NOT NULL,
                    payload TEXT NOT NULL, outreach TEXT, UNIQUE(mandate_id, company_id));
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id),
                    source_key TEXT NOT NULL UNIQUE, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS case_evidence (
                    case_id TEXT NOT NULL REFERENCES cases(id), evidence_id TEXT NOT NULL REFERENCES evidence(id),
                    PRIMARY KEY(case_id, evidence_id));
                CREATE TABLE IF NOT EXISTS evaluations (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
                    case_id TEXT NOT NULL REFERENCES cases(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
                    case_id TEXT NOT NULL REFERENCES cases(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, mandate_id TEXT NOT NULL REFERENCES mandates(id),
                    status TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_task ON tasks(mandate_id)
                    WHERE status IN ('pending', 'running');
                CREATE INDEX IF NOT EXISTS case_mandates ON cases(mandate_id);
                CREATE INDEX IF NOT EXISTS case_evaluations ON evaluations(case_id, sequence);
                CREATE INDEX IF NOT EXISTS case_events ON events(case_id, sequence);
                CREATE TABLE IF NOT EXISTS mandate_policy_refs (
                    mandate_id TEXT PRIMARY KEY REFERENCES mandates(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS case_assessment_state (
                    case_id TEXT PRIMARY KEY REFERENCES cases(id), pending INTEGER NOT NULL,
                    current_gaps TEXT NOT NULL, accepted_evaluation_id TEXT,
                    last_error TEXT, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS assessment_invocations (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    snapshot_id TEXT NOT NULL UNIQUE, snapshot_json TEXT NOT NULL,
                    status TEXT NOT NULL, replayed INTEGER NOT NULL,
                    task_id TEXT REFERENCES tasks(id), evaluation_id TEXT,
                    proposal_json TEXT, error_code TEXT, error_message TEXT,
                    failure_notified INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS assessment_case_status ON assessment_invocations(case_id,status);
                CREATE TABLE IF NOT EXISTS discovery_approvals (
                    id TEXT PRIMARY KEY, mandate_id TEXT NOT NULL REFERENCES mandates(id),
                    payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS discovery_executions (
                    id TEXT PRIMARY KEY, approval_id TEXT NOT NULL REFERENCES discovery_approvals(id),
                    attempt_key TEXT NOT NULL, task_id TEXT NOT NULL REFERENCES tasks(id), status TEXT NOT NULL,
                    result_slots INTEGER NOT NULL, quoted_microcredits INTEGER NOT NULL,
                    result_count INTEGER, candidates_json TEXT, error TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(approval_id,attempt_key));
                CREATE TABLE IF NOT EXISTS evidence_discovery_refs (
                    evidence_id TEXT NOT NULL REFERENCES evidence(id),
                    execution_id TEXT NOT NULL REFERENCES discovery_executions(id),
                    payload TEXT NOT NULL, PRIMARY KEY(evidence_id,execution_id));
                CREATE TABLE IF NOT EXISTS discovery_encounters (
                    execution_id TEXT NOT NULL REFERENCES discovery_executions(id),
                    company_source_key TEXT NOT NULL, company_id TEXT NOT NULL REFERENCES companies(id),
                    case_id TEXT NOT NULL REFERENCES cases(id), payload TEXT NOT NULL,
                    PRIMARY KEY(execution_id,company_source_key));
                CREATE TABLE IF NOT EXISTS semantic_assessments (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    invocation_id TEXT NOT NULL UNIQUE REFERENCES assessment_invocations(id),
                    payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS qualification_reviews (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    assessment_id TEXT NOT NULL REFERENCES semantic_assessments(id),
                    request_key TEXT NOT NULL UNIQUE, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_graph_snapshots (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS case_research_packets (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_decisions (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    assessment_id TEXT NOT NULL UNIQUE REFERENCES semantic_assessments(id),
                    payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS scout_batches (
                    id TEXT PRIMARY KEY, mandate_id TEXT NOT NULL REFERENCES mandates(id),
                    payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS scout_batch_candidates (
                    id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES scout_batches(id),
                    identity_key TEXT NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(batch_id,identity_key));
                CREATE TABLE IF NOT EXISTS case_briefs (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
                    assessment_id TEXT NOT NULL REFERENCES semantic_assessments(id),
                    payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_followup_links (
                    case_id TEXT NOT NULL,assessment_id TEXT NOT NULL,payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,PRIMARY KEY(case_id,assessment_id));
                CREATE TABLE IF NOT EXISTS research_execution_tasks (
                    id TEXT PRIMARY KEY,case_id TEXT NOT NULL,assessment_id TEXT NOT NULL,
                    payload TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pre_outreach_reviews (
                    id TEXT PRIMARY KEY,case_id TEXT NOT NULL REFERENCES cases(id),
                    assessment_id TEXT NOT NULL REFERENCES semantic_assessments(id),
                    binding_key TEXT NOT NULL UNIQUE,payload TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS scouting_runs (
                    id TEXT PRIMARY KEY,idempotency_key TEXT NOT NULL UNIQUE,status TEXT NOT NULL,
                    payload TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_scouting_loop ON scouting_runs((1))
                    WHERE status IN ('queued','running','stopping');
                PRAGMA user_version=4;
            """)
            # Additive v1 -> v2 backfill: preserve existing accepted history and
            # do not reassess unchanged legacy cases merely because of migration.
            for row in db.execute("SELECT id FROM cases").fetchall():
                previous = db.execute("SELECT payload FROM evaluations WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (row[0],)).fetchone()
                evaluation = Evaluation.model_validate_json(previous[0]) if previous else None
                db.execute("INSERT OR IGNORE INTO case_assessment_state VALUES (?,?,?,?,?,?)", (row[0], int(evaluation is None), json.dumps(evaluation.missing_claims if evaluation else []), evaluation.id if evaluation else None, None, now()))

    @staticmethod
    def _read(db, table, model, id):
        row = db.execute(f"SELECT payload FROM {table} WHERE id=?", (id,)).fetchone()
        if row is None:
            raise ServiceError("not_found", f"{model.__name__} not found", 404)
        return model.model_validate_json(row["payload"])

    @staticmethod
    def _put_mandate(db, mandate):
        db.execute("UPDATE mandates SET payload=? WHERE id=?", (mandate.model_dump_json(), mandate.id))

    @staticmethod
    def _put_task(db, task):
        db.execute("UPDATE tasks SET status=?, payload=? WHERE id=?", (task.status, task.model_dump_json(), task.id))

    def create_mandate(self, request: CreateMandate) -> Mandate:
        stamp = now()
        mandate = Mandate(**request.model_dump(), id=uid("mandate"), created_at=stamp, updated_at=stamp)
        with self.connection(write=True) as db:
            db.execute("INSERT INTO mandates VALUES (?,?)", (mandate.id, mandate.model_dump_json()))
        return mandate

    def mandates(self):
        with self.connection() as db:
            return [Mandate.model_validate_json(r[0]) for r in db.execute("SELECT payload FROM mandates ORDER BY rowid")]

    def mandate(self, id):
        with self.connection() as db:
            return self._read(db, "mandates", Mandate, id)

    def task(self, id):
        with self.connection() as db:
            return self._read(db, "tasks", Task, id)

    def cases(self, mandate_id):
        with self.connection() as db:
            self._read(db, "mandates", Mandate, mandate_id)
            return [Case.model_validate_json(r[0]) for r in db.execute("SELECT payload FROM cases WHERE mandate_id=? ORDER BY rowid", (mandate_id,))]

    @staticmethod
    def _evidence(db, case_id):
        evidence = []
        for row in db.execute("SELECT e.id,e.company_id,e.source_key,e.payload FROM evidence e JOIN case_evidence ce ON e.id=ce.evidence_id WHERE ce.case_id=? ORDER BY e.rowid", (case_id,)):
            observation = Evidence.model_validate_json(row["payload"])
            if observation.id != row["id"] or observation.company_id != row["company_id"] or observation.source_key != row["source_key"]:
                raise ServiceError("invalid_evidence", "Evidence identity/provenance does not match its stored ownership", 422)
            evidence.append(observation)
        return evidence

    def _detail(self, db, case_id):
        case = self._read(db, "cases", Case, case_id)
        row = db.execute("SELECT outreach FROM cases WHERE id=?", (case_id,)).fetchone()
        context = self._assessment_context(db, case_id)
        versions = context.versions.model_dump(mode="json")
        research=context.research_context or {}
        people=[]
        for person in research.get('people',[]):
            roles=[r for r in research.get('relationships',[]) if r['person_id']==person['id']]
            ids=list(dict.fromkeys([eid for r in roles for eid in r['evidence_ids']]+[eid for eid,s in research.get('subjects',{}).items() if s['kind']=='person' and s['id']==person['id']]))
            people.append({**person,'case_version':case.version,'evidence_ids':ids,'roles':roles,'attribution':'Saved source-reported identity/roles; independent verification and tenure are not implied.'})
        assessments, reviews = [], []
        for stored in db.execute("SELECT * FROM semantic_assessments WHERE case_id=? ORDER BY rowid", (case_id,)):
            data = json.loads(stored["payload"])
            result = data["result"]
            assessments.append({"id": stored["id"], "outcome": result["outcome"], "proposed_disposition": result.get("disposition"), "driver_kind": result["driver_kind"], "prompt_version": result.get("prompt_version", "unknown"), "comparison_only": data["classification"] != "recommendation", "eligible_for_human_review": data["eligible"], "input_current": data["backend_versions"] == versions, "expected_case_version": case.version, "created_at": stored["created_at"], "structured_result": result, "review_eligibility": data["review_eligibility"]})
        for stored in db.execute("SELECT payload FROM qualification_reviews WHERE case_id=? ORDER BY rowid", (case_id,)):
            review = json.loads(stored[0])
            reviews.append({k: review[k] for k in ("id", "assessment_id", "decision", "note", "reviewer_identity", "source", "synthetic_test", "created_at")} | {"current": review["post_versions"] == versions})
        return CaseDetail(
            **case.model_dump(), evidence=self._evidence(db, case_id),
            evaluations=[Evaluation.model_validate_json(r[0]) for r in db.execute("SELECT payload FROM evaluations WHERE case_id=? ORDER BY sequence", (case_id,))],
            events=[Event.model_validate_json(r[0]) for r in db.execute("SELECT payload FROM events WHERE case_id=? ORDER BY sequence", (case_id,))],
            outreach=OutreachPackage.model_validate_json(row[0]) if row[0] else None,
            agent_assessments=assessments, qualification_reviews=reviews, people=people,
        )

    def detail(self, case_id):
        with self.connection(snapshot=True) as db:
            return self._detail(db, case_id)

    def enqueue_run(self, mandate_id):
        with self.connection(write=True) as db:
            mandate = self._read(db, "mandates", Mandate, mandate_id)
            active = db.execute("SELECT payload FROM tasks WHERE mandate_id=? AND status IN ('pending','running')", (mandate_id,)).fetchone()
            if active:
                return Task.model_validate_json(active[0]), False
            count = db.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('pending','running')").fetchone()[0]
            if count >= 16:
                raise ServiceError("task_capacity_exceeded", "Local task capacity reached; wait for a task to finish", 429, True)
            stamp = now()
            task = Task(id=uid("task"), mandate_id=mandate_id, type="discover_and_evaluate", status="pending", created_at=stamp, updated_at=stamp)
            db.execute("INSERT INTO tasks VALUES (?,?,?,?)", (task.id, mandate_id, task.status, task.model_dump_json()))
            mandate.status, mandate.updated_at = "running", stamp
            self._put_mandate(db, mandate)
            return task, True

    def start_task(self, task_id):
        with self.connection(write=True) as db:
            task = self._read(db, "tasks", Task, task_id)
            if task.status != "pending":
                raise ServiceError("invalid_transition", "Only pending tasks may start", 409)
            task.status, task.updated_at = "running", now()
            self._put_task(db, task)
            return task

    def fail_task(self, task_id, message):
        with self.connection(write=True) as db:
            task = self._read(db, "tasks", Task, task_id)
            task.status, task.error, task.updated_at = "failed", message, now()
            self._put_task(db, task)
            mandate = self._read(db, "mandates", Mandate, task.mandate_id)
            mandate.status, mandate.updated_at = "failed", now()
            self._put_mandate(db, mandate)

    def recover_interrupted_tasks(self):
        # This is deliberately a SINGLE PROCESS runner: other active app instances
        # sharing the database would incorrectly be considered interrupted.
        with self.connection() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM tasks WHERE status IN ('pending','running')")]
        for task_id in ids:
            self.fail_task(task_id, "Interrupted before completion. Local in-process tasks are not durable; rerun the mandate to retry safely.")
        with self.connection() as db:
            invocations = [r[0] for r in db.execute("SELECT id FROM assessment_invocations WHERE status='running'")]
        for invocation_id in invocations:
            self.record_assessment_failure(invocation_id, "assessment_interrupted", "Assessment was interrupted. Saved observations remain pending; rerun the mandate or repeat its catalog replay.")
        with self.connection(write=True) as db:
            db.execute("UPDATE discovery_executions SET status='interrupted',error=?,updated_at=? WHERE status='running'", ("Search execution interrupted; billed usage is unknown. Reservation retained and no automatic retry authorized.", now()))
        return len(ids)

    @staticmethod
    def _event(db, case_id, event_type, summary, evidence_ids, replayed=False, data_mode="synthetic"):
        event = Event(id=uid("event"), case_id=case_id, event_type=event_type, created_at=now(), summary=summary, evidence_ids=evidence_ids, replayed=replayed, data_mode=data_mode)
        db.execute("INSERT INTO events(id,case_id,payload) VALUES (?,?,?)", (event.id, case_id, event.model_dump_json()))

    def _assessment_context(self, db, case_id, snapshot_id=None, captured_at=None):
        case = self._read(db, "cases", Case, case_id)
        mandate = self._read(db, "mandates", Mandate, case.mandate_id)
        company_row = db.execute("SELECT * FROM companies WHERE id=?", (case.company_id,)).fetchone()
        company_payload = json.loads(company_row["payload"])
        evidence = self._evidence(db, case_id)
        if any(e.company_id != case.company_id for e in evidence):
            raise ServiceError("invalid_evidence", "Case contains evidence attributed to a different company", 422)
        prior_row = db.execute("SELECT payload FROM evaluations WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,)).fetchone()
        prior = Evaluation.model_validate_json(prior_row[0]) if prior_row else None
        state = db.execute("SELECT current_gaps FROM case_assessment_state WHERE case_id=?", (case_id,)).fetchone()
        gaps = tuple(json.loads(state[0])) if state else tuple(prior.missing_claims if prior else [])
        policy_row = db.execute("SELECT payload FROM mandate_policy_refs WHERE mandate_id=?", (mandate.id,)).fetchone()
        policy = PolicyReference.model_validate_json(policy_row[0]) if policy_row else PolicyReference()
        research_row = db.execute("SELECT payload FROM case_research_packets WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,)).fetchone()
        research = json.loads(research_row[0]) if research_row else None
        versions = InputVersions(
            case_id=case.id, mandate_id=mandate.id, company_id=case.company_id,
            case_version=case.version, case_content_version=content_version(case),
            thesis_version=mandate.thesis_version,
            thesis_content_version=content_version({k: getattr(mandate, k) for k in ("title", "thesis_text", "thesis_version", "reference_status", "target_count")}),
            policy=policy, policy_content_version=content_version(policy),
            company_content_version=content_version(dict(company_row)),
            evidence_manifest=tuple(EvidenceManifestEntry(evidence_id=e.id, company_id=e.company_id, content_version=content_version(e)) for e in sorted(evidence, key=lambda e: e.id)),
            prior_evaluation_id=prior.id if prior else None,
            prior_findings_version=content_version({"evaluation": prior.model_dump(mode="json") if prior else None, "gaps": gaps}),
            reference_content_version=content_version(self.reference_material) if self.reference_material is not None else None,
            research_content_version=content_version(research) if research else None,
        )
        return AssessmentContext(
            snapshot_id=snapshot_id or uid("snapshot"), captured_at=captured_at or now(), versions=versions,
            case=case, mandate=mandate,
            company=CompanyContext(id=case.company_id, source_key=company_row["source_key"], name=company_payload["company_name"], canonical_domain=company_row["canonical_domain"], data_mode=company_payload["data_mode"]),
            evidence=tuple(evidence), prior_evaluation=prior, prior_findings=tuple(prior.dimensions if prior else []), current_gaps=gaps,
            people=UnavailableContext(status="partial" if research and research.get("people") else "unavailable", reason="Bounded source-reported people from the saved research packet; no people-API or complete-team coverage is implied." if research else "No sourced team/person-profile store or verified people adapter is installed. Fixture outreach contacts are not founding-team evidence."),
            relationships=UnavailableContext(status="partial" if research and research.get("relationships") else "unavailable", reason="Saved source-reported attribution only; role dates/completeness may be unknown." if research else "No sourced person/company role-tenure relationships are available."),
            market=UnavailableContext(reason="No separate sourced market context is available; company claims are not a market model."),
            reference_material=self.reference_material,
            research_context=research,
        )

    def load_assessment_context(self, case_id) -> AssessmentContext:
        with self.connection(snapshot=True) as db:
            context = self._assessment_context(db, case_id)
        # All models/JSON are detached; no cursor, lazy query or connection escapes.
        return context

    def begin_assessment(self, context, *, replayed=False, task_id=None):
        invocation_id, stamp = uid("invocation"), now()
        with self.connection(write=True) as db:
            if task_id:
                task = self._read(db, "tasks", Task, task_id)
                if task.mandate_id != context.mandate.id or task.status != "running":
                    raise ServiceError("invalid_transition", "Assessment parent task must be running for the same mandate", 409)
            db.execute("INSERT INTO assessment_invocations(id,case_id,snapshot_id,snapshot_json,status,replayed,task_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (invocation_id, context.case.id, context.snapshot_id, context.model_dump_json(), "running", int(replayed), task_id, stamp, stamp))
        return invocation_id

    @staticmethod
    def _validate_proposal(context, proposal):
        result = proposal.result
        allowed = {e.evidence_id for e in context.versions.evidence_manifest}
        cited = set(result.evidence_ids)
        for finding in result.dimensions:
            cited.update(finding.evidence_ids)
            if finding.status in {"supported", "contradicted"} and not finding.evidence_ids:
                raise ServiceError("invalid_evidence", "Supported or contradicted findings require supplied evidence references", 422)
        if result.investigation:
            if result.investigation.case_id != context.case.id:
                raise ServiceError("invalid_proposal", "Investigation suggestion must be scoped to the assessed case", 422)
            cited.update(result.investigation.evidence_ids)
        if not cited.issubset(allowed):
            raise ServiceError("invalid_evidence", "Proposal cites evidence outside the supplied case manifest", 422)
        if result.evaluator_kind != "fixture" or result.data_mode != "synthetic":
            raise ServiceError("invalid_transition", "Only the explicitly labeled fixture/development evaluator is enabled; semantic policy/runtime is not activated", 409)
        fixture_case = context.case.data_mode == "synthetic" and context.company.source_key.startswith("fixture:")
        if not fixture_case and (result.recommendation not in {"needs_evidence", "monitor"} or result.thesis_fit is not None or result.evidence_sufficiency is not None or result.outreach is not None):
            raise ServiceError("invalid_transition", "Development placeholders cannot score, qualify, reject or prepare outreach for genuine company cases", 409)
        if result.outreach and (result.outreach.data_mode != "synthetic" or (result.outreach.person and result.outreach.person.data_mode != "synthetic")):
            raise ServiceError("invalid_transition", "Fixture outreach and contacts must remain synthetic", 409)
        if result.recommendation == "outreach_ready" and result.outreach is None:
            raise ServiceError("invalid_transition", "Outreach-ready fixture requires its labeled package", 409)

    def accept_assessment(self, proposal: AssessmentProposal) -> Evaluation:
        proposal = AssessmentProposal.model_validate_json(proposal.model_dump_json())
        error, accepted = None, None
        with self.connection(write=True) as db:
            invocation = db.execute("SELECT * FROM assessment_invocations WHERE id=?", (proposal.invocation_id,)).fetchone()
            if not invocation:
                raise ServiceError("not_found", "Assessment invocation not found", 404)
            if invocation["status"] == "accepted":
                previous_proposal = AssessmentProposal.model_validate_json(invocation["proposal_json"])
                if previous_proposal != proposal:
                    raise ServiceError("invalid_transition", "Accepted invocation cannot be replaced by another proposal", 409)
                return self._read(db, "evaluations", Evaluation, invocation["evaluation_id"])
            if invocation["status"] != "running":
                raise ServiceError("invalid_transition", "Assessment invocation is no longer running; build a fresh snapshot to retry", 409)
            saved = AssessmentContext.model_validate_json(invocation["snapshot_json"])
            try:
                current = self._assessment_context(db, saved.case.id)
                if proposal.snapshot_id != saved.snapshot_id or proposal.input_versions != saved.versions or current.versions != saved.versions:
                    raise ServiceError("stale_version", "Assessment inputs changed. Current judgment was retained; retry against a fresh snapshot.", 409, True)
                if invocation["task_id"]:
                    task = self._read(db, "tasks", Task, invocation["task_id"])
                    if task.status != "running" or task.mandate_id != saved.mandate.id:
                        raise ServiceError("stale_version", "Assessment parent task is no longer running. Current judgment was retained.", 409, True)
                self._validate_proposal(saved, proposal)
                if db.execute("SELECT 1 FROM semantic_assessments WHERE case_id=? LIMIT 1", (saved.case.id,)).fetchone() and proposal.result.recommendation in {"qualified", "outreach_ready"}:
                    raise ServiceError("invalid_transition", "Agent-review cases require explicit current human qualification; legacy fixture acceptance cannot promote them", 409)
                result, case = proposal.result, current.case
                accepted = Evaluation(id=uid("evaluation"), case_id=case.id, thesis_version=current.mandate.thesis_version, created_at=now(), **result.model_dump(exclude={"outreach", "investigation"}))
                db.execute("INSERT INTO evaluations(id,case_id,payload) VALUES (?,?,?)", (accepted.id, case.id, accepted.model_dump_json()))
                case.status, case.version = accepted.recommendation, case.version + 1
                case.thesis_fit, case.evidence_sufficiency = accepted.thesis_fit, accepted.evidence_sufficiency
                case.next_action, case.updated_at = accepted.next_action, now()
                db.execute("UPDATE cases SET payload=?,outreach=? WHERE id=?", (case.model_dump_json(), result.outreach.model_dump_json() if result.outreach else None, case.id))
                db.execute("UPDATE case_assessment_state SET pending=0,current_gaps=?,accepted_evaluation_id=?,last_error=NULL,updated_at=? WHERE case_id=?", (json.dumps(accepted.missing_claims), accepted.id, now(), case.id))
                self._event(db, case.id, "evaluation_completed", f"Accepted fixture/development evaluation {accepted.id}: {case.status.value}. " + accepted.reasoning_summary, accepted.evidence_ids, bool(invocation["replayed"]), accepted.data_mode)
                self._reconcile(db, current.mandate)
                db.execute("UPDATE assessment_invocations SET status='accepted',evaluation_id=?,proposal_json=?,updated_at=? WHERE id=?", (accepted.id, proposal.model_dump_json(), now(), proposal.invocation_id))
            except ServiceError as rejected:
                error = rejected
                db.execute("UPDATE assessment_invocations SET status=?,error_code=?,error_message=?,updated_at=? WHERE id=?", ("stale" if error.code == "stale_version" else "invalid", error.code, error.message, now(), proposal.invocation_id))
        if error:
            raise error
        return accepted

    def record_assessment_failure(self, invocation_id, code, message):
        with self.connection(write=True) as db:
            invocation = db.execute("SELECT * FROM assessment_invocations WHERE id=?", (invocation_id,)).fetchone()
            if not invocation or invocation["status"] == "accepted" or invocation["failure_notified"]:
                return
            context = AssessmentContext.model_validate_json(invocation["snapshot_json"])
            status = invocation["status"] if invocation["status"] in {"stale", "invalid"} else "failed"
            db.execute("UPDATE assessment_invocations SET status=?,error_code=?,error_message=?,failure_notified=1,updated_at=? WHERE id=?", (status, code, message, now(), invocation_id))
            db.execute("UPDATE case_assessment_state SET last_error=?,updated_at=? WHERE case_id=? AND pending=1", (message, now(), context.case.id))
            self._event(db, context.case.id, "assessment_failed", f"Operational assessment outcome ({code}): {message}", [], bool(invocation["replayed"]), context.case.data_mode)

    def _reconcile(self, db, mandate):
        cases = [Case.model_validate_json(r[0]) for r in db.execute("SELECT payload FROM cases WHERE mandate_id=?", (mandate.id,))]
        mandate.progress = Progress(total=len(cases), outreach_ready=sum(c.status == "outreach_ready" for c in cases))
        active = db.execute("SELECT 1 FROM tasks WHERE mandate_id=? AND status IN ('pending','running')", (mandate.id,)).fetchone()
        mandate.status = "running" if active else ("completed" if mandate.progress.outreach_ready >= mandate.target_count else "shortfall")
        mandate.updated_at = now()
        self._put_mandate(db, mandate)

    def _invalidate_human_review(self, db, case):
        if case.status in {"qualified", "outreach_ready"} and db.execute("SELECT 1 FROM qualification_reviews WHERE case_id=? LIMIT 1", (case.id,)).fetchone():
            from .models import CaseStatus
            case.status = CaseStatus.needs_evidence
            case.next_action = "New evidence invalidated the prior human review; reassess before qualification."
            db.execute("UPDATE cases SET outreach=NULL WHERE id=?", (case.id,))
            self._event(db, case.id, "qualification_review_stale", "New observation invalidated the previous version-bound human qualification. Historical approval remains saved.", [], data_mode=case.data_mode)

    def persist_discovery(self, task_id, candidates):
        with self.connection(write=True) as db:
            task = self._read(db, "tasks", Task, task_id)
            if task.status != "running":
                raise ServiceError("invalid_transition", "Only running tasks can complete", 409)
            mandate = self._read(db, "mandates", Mandate, task.mandate_id)
            for candidate in candidates:
                domain = candidate.canonical_domain.lower().strip().rstrip(".") if candidate.canonical_domain else None
                company_source = f"{candidate.provider}:{candidate.key}"
                scenario_key = candidate.key if candidate.provider == "fixture" else company_source
                company = db.execute("SELECT id FROM companies WHERE source_key=? OR canonical_domain=?", (company_source, domain)).fetchone()
                company_id = company[0] if company else uid("company")
                if not company:
                    db.execute("INSERT INTO companies VALUES (?,?,?,?)", (company_id, company_source, domain, json.dumps({"company_name": candidate.company_name, "data_mode": candidate.data_mode, "provider_company_id": candidate.provider_company_id, "description": candidate.description})))
                existing = db.execute("SELECT id FROM cases WHERE mandate_id=? AND company_id=?", (mandate.id, company_id)).fetchone()
                if existing:
                    case = self._read(db, "cases", Case, existing[0])
                else:
                    case = Case(id=uid("case"), mandate_id=mandate.id, company_id=company_id, company_name=candidate.company_name, canonical_domain=domain, status="discovered", version=0, next_action="Assess available evidence", data_mode=candidate.data_mode, updated_at=now())
                    db.execute("INSERT INTO cases VALUES (?,?,?,?,?,?)", (case.id, mandate.id, company_id, scenario_key, case.model_dump_json(), None))
                    db.execute("INSERT INTO case_assessment_state VALUES (?,?,?,?,?,?)", (case.id, 1, "[]", None, None, now()))
                changed = False
                evidence_ids = []
                for index, item in enumerate(candidate.evidence):
                    source_key = item.get("source_key") or f"fixture:{candidate.key}:seed:{index}"
                    existing_evidence = db.execute("SELECT id FROM evidence WHERE source_key=?", (source_key,)).fetchone()
                    if existing_evidence:
                        evidence_id = existing_evidence[0]
                    else:
                        evidence = Evidence(id=uid("evidence"), company_id=company_id, claim_type=item["claim_type"], summary=item["summary"], source_url=item.get("source_url"), source_key=source_key, observed_at=item.get("observed_at"), retrieved_at=item.get("retrieved_at") or now(), data_mode=item.get("data_mode", candidate.data_mode))
                        evidence_id = evidence.id
                        db.execute("INSERT INTO evidence VALUES (?,?,?,?)", (evidence.id, company_id, source_key, evidence.model_dump_json()))
                    linked = db.execute("INSERT OR IGNORE INTO case_evidence VALUES (?,?)", (case.id, evidence_id))
                    changed |= bool(linked.rowcount)
                    if candidate.discovery_refs:
                        refs = candidate.discovery_refs
                        db.execute("INSERT OR IGNORE INTO evidence_discovery_refs VALUES (?,?,?)", (evidence_id, refs["execution_id"], json.dumps(refs)))
                    evidence_ids.append(evidence_id)
                if candidate.discovery_refs:
                    refs = candidate.discovery_refs
                    db.execute("INSERT OR IGNORE INTO discovery_encounters VALUES (?,?,?,?,?)", (refs["execution_id"], company_source, company_id, case.id, json.dumps(refs)))
                if not existing or changed:
                    discovery_summary = "Explicit synthetic fixture discovery; no live company or source verification." if candidate.provider == "fixture" else "Company fields returned by authenticated Crustdata search; discovery lead only, not product proof, YC novelty or qualification."
                    if candidate.discovery_refs:
                        discovery_summary += f" Reviewed branch {candidate.discovery_refs['branch_id']}; track is a search hypothesis, not company classification."
                    self._event(db, case.id, "discovery_observation_received" if existing else "company_discovered", discovery_summary, evidence_ids, data_mode=candidate.data_mode)
                    if existing:
                        self._invalidate_human_review(db, case)
                        case.version, case.updated_at = case.version + 1, now()
                        db.execute("UPDATE cases SET payload=? WHERE id=?", (case.model_dump_json(), case.id))
                        db.execute("UPDATE case_assessment_state SET pending=1,last_error=NULL,updated_at=? WHERE case_id=?", (now(), case.id))
            self._reconcile(db, mandate)
            return [r[0] for r in db.execute("SELECT c.id FROM cases c JOIN case_assessment_state a ON c.id=a.case_id WHERE c.mandate_id=? AND a.pending=1 ORDER BY c.rowid", (mandate.id,))]

    def complete_task(self, task_id):
        with self.connection(write=True) as db:
            task = self._read(db, "tasks", Task, task_id)
            if task.status != "running":
                raise ServiceError("invalid_transition", "Only running tasks can complete", 409)
            mandate = self._read(db, "mandates", Mandate, task.mandate_id)
            if db.execute("SELECT 1 FROM case_assessment_state a JOIN cases c ON c.id=a.case_id WHERE c.mandate_id=? AND a.pending=1 LIMIT 1", (mandate.id,)).fetchone():
                raise ServiceError("stale_version", "Saved cases still await assessment; rerun to retry pending work", 409, True)
            task.status, task.updated_at = "succeeded", now()
            self._put_task(db, task)
            self._reconcile(db, mandate)

    def ingest_replay(self, case_id, signal: SignalInput, catalog) -> bool:
        with self.connection(write=True) as db:
            case = self._read(db, "cases", Case, case_id)
            fixture_key = db.execute("SELECT fixture_key FROM cases WHERE id=?", (case_id,)).fetchone()[0]
            replay = catalog.replay(fixture_key, signal)
            if signal.data_mode == "captured" and not replay:
                raise ServiceError("validation_error", "Captured replay must match a registered genuine capture. No captured provider signals are registered in this harness.", 422)
            if replay:
                source_key = f"fixture:{fixture_key}:signal:{replay['key']}"
                existing = db.execute("SELECT e.id FROM evidence e JOIN case_evidence ce ON e.id=ce.evidence_id WHERE ce.case_id=? AND e.source_key=?", (case_id, source_key)).fetchone()
                if existing:
                    # No duplicate observation/event. Failed prior assessment can retry.
                    return bool(db.execute("SELECT pending FROM case_assessment_state WHERE case_id=?", (case_id,)).fetchone()[0])
                # A company may be used by multiple mandates; link its capture to
                # each case while retaining one immutable company observation.
                observation = db.execute("SELECT id FROM evidence WHERE source_key=?", (source_key,)).fetchone()
            else:
                source_key, observation = f"synthetic-unverified:{uid('replay')}", None
            evidence = Evidence(id=observation[0] if observation else uid("evidence"), company_id=case.company_id, claim_type=signal.claim_type, summary=signal.summary, source_url=signal.source_url, source_key=source_key, retrieved_at=now(), data_mode=signal.data_mode)
            if not observation:
                db.execute("INSERT INTO evidence VALUES (?,?,?,?)", (evidence.id, case.company_id, source_key, evidence.model_dump_json()))
            db.execute("INSERT INTO case_evidence VALUES (?,?)", (case.id, evidence.id))
            label = "Catalog synthetic replay" if replay else "Unverified synthetic replay; does not establish live evidence"
            self._event(db, case.id, "signal_replayed", f"{label}: {signal.summary}", [evidence.id], True)
            case.why_now = f"Synthetic replay: {signal.summary}" if replay else case.why_now
            self._invalidate_human_review(db, case)
            case.version, case.updated_at = case.version + 1, now()
            db.execute("UPDATE cases SET payload=? WHERE id=?", (case.model_dump_json(), case.id))
            db.execute("UPDATE case_assessment_state SET pending=1,last_error=NULL,updated_at=? WHERE case_id=?", (now(), case.id))
            self._reconcile(db, self._read(db, "mandates", Mandate, case.mandate_id))
            return True
