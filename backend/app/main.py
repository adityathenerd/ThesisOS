from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .errors import ServiceError
from .evaluators import FixtureEvaluator, FixtureEvaluatorAdapter
from .assessments import AssessmentCoordinator, load_reference_material
from .models import CaseDetail, CaseList, ConfigStatus, CreateMandate, ErrorResponse, EvaluationList, Health, Mandate, MandateList, QualificationReviewInput, SignalInput, Task
from .agent_bridge import AgentAssessmentStore
from .research_graph import saved_research_graph, scout_result
from .providers import CrustdataSearchProvider, FixtureCatalog, build_provider
from .runner import InProcessRunner
from .settings import APP_ROOT, Settings
from .state import StateService
from .discovery import ApprovedCompanySearchProvider, DiscoveryStore
from .batch import BatchStore
from .follow_up import research_follow_up,execute_research_intent
from .models import ResearchExecutionInput
from .pre_outreach import pre_outreach_review
from .scouting_loop import ScoutingLoop,RunStore,StartScoutingRun


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    reference = load_reference_material(APP_ROOT, settings.reference_source_config)
    state = StateService(settings.sqlite_path(), reference_material=reference)
    catalog = FixtureCatalog(settings.fixture_path)
    provider = build_provider(settings, catalog, state)
    evaluator = FixtureEvaluator(catalog)
    assessments = AssessmentCoordinator(state, FixtureEvaluatorAdapter(evaluator))

    @asynccontextmanager
    async def lifespan(app):
        app.state.runtime_ready=False
        state.initialize()
        app.state.recovered_task_count = state.recover_interrupted_tasks()
        app.state.runner = InProcessRunner(state, provider, assessments, settings.max_cases_per_run)
        app.state.scouting_loop=ScoutingLoop(state,settings)
        app.state.scouting_loop.recover()
        app.state.runtime_ready=True
        yield
        app.state.runtime_ready=False
        app.state.scouting_loop.close()
        app.state.runner.close()

    app = FastAPI(title="ThesisOS local harness", version="0.1", lifespan=lifespan, responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
    app.state.service = state
    app.state.assessments = assessments
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"], allow_credentials=False)

    def error_response(code, message, status, retryable=False):
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "retryable": retryable}})

    @app.exception_handler(ServiceError)
    async def handle_service_error(request, error):
        return error_response(error.code, error.message, error.status, error.retryable)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request, error):
        # No raw input or full Pydantic error object (which can echo secrets/text).
        fields = ", ".join(".".join(str(part) for part in item["loc"]) for item in error.errors())
        return error_response("validation_error", f"Request validation failed at: {fields}. See /docs for accepted types and signal replay requirements.", 422)

    @app.exception_handler(HTTPException)
    async def handle_http_error(request, error):
        return error_response("not_found" if error.status_code == 404 else "validation_error", "Route not found" if error.status_code == 404 else "HTTP request could not be processed", error.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected(request, error):
        return error_response("internal_error", "The local service could not complete this request. Check server state and retry.", 500, True)

    @app.get("/health", response_model=Health)
    def health():
        # Verify persistence is available instead of returning a static process badge.
        with state.connection() as db:
            db.execute("SELECT 1 FROM mandates LIMIT 1").fetchone()
        return Health()

    @app.get('/api/v1/runtime/status')
    def runtime_status():
        return {'lifespan_ready':getattr(app.state,'runtime_ready',False),'pid':os.getpid(),'recovered_task_count':getattr(app.state,'recovered_task_count',0)}

    @app.get('/api/v1/scouting-runs')
    def scouting_runs():
        return {'items':RunStore(state).list()}

    @app.post('/api/v1/scouting-runs')
    def start_scouting_run(request:StartScoutingRun):
        if not getattr(app.state,'runtime_ready',False):raise ServiceError('runtime_not_ready','Wait for serving startup recovery before starting a run',409)
        return app.state.scouting_loop.start(request)

    @app.get('/api/v1/scouting-runs/{run_id}')
    def scouting_run(run_id:str):
        return RunStore(state).get(run_id)

    @app.post('/api/v1/scouting-runs/{run_id}/stop')
    def stop_scouting_run(run_id:str):
        return app.state.scouting_loop.stop(run_id)

    @app.get("/api/v1/config/status", response_model=ConfigStatus)
    def config_status():
        query_status, query_label = "awaiting_configuration", None
        if settings.crustdata_search_config:
            try:
                live = ApprovedCompanySearchProvider(settings, state)
                selection = live.configuration()
                reviewed = live.store.reviewed(selection.approval_id)
                query_status, query_label = "reviewed_discovery_only", reviewed["compiled"]["branch"]["hypothesis"]["hypothesis"]
            except ServiceError:
                query_status = "unapproved_or_access_test_configuration"
        return ConfigStatus(
            provider_mode=settings.provider_mode,
            crustdata_configured=bool(settings.crustdata_api_key.strip()),
            thesis_status="user_supplied" if any(m.reference_status == "user_supplied" for m in state.mandates()) else "awaiting_reference",
            max_cases_per_run=settings.max_cases_per_run,
            discovery_query_status=query_status,
            discovery_query_label=query_label,
            limitations=[
                "All fixture company facts, people, scores and dispositions are synthetic.",
                "Fixture evaluator does not interpret the thesis. User-supplied text is not reviewed or approved criteria.",
                "One documented ranked Company Search and one genuine compiled matcher comparison are saved for the first scout. This does not establish people/enrichment access or discovery quality across tracks.",
                "Live sourcing requires a thesis-linked backend-registered discovery-only approval, verified catalog and reservation. The headcount access-test JSON is not a sourcing funnel. Default runner still uses the fixture/development evaluator; rich explicit-CLI agent comparisons remain separate from accepted qualification.",
                "Run one backend process with one worker per database. Interrupted in-process tasks are marked failed on startup; rerun to retry.",
                "Local unauthenticated demo API; no outreach sending or durable monitoring.",
                "Assessments use detached snapshots and conditional acceptance. Saved candidates/observations survive evaluator failure; pending assessments are retryable, not investment rejection.",
            ],
        )

    @app.get("/api/v1/mandates", response_model=MandateList)
    def mandates():
        return MandateList(items=state.mandates())

    @app.get('/api/v1/research-batches')
    def research_batches():
        return {'items':BatchStore(state).list()}

    @app.get('/api/v1/research-batches/{batch_id}')
    def research_batch(batch_id:str):
        return BatchStore(state).get(batch_id)

    @app.get('/api/v1/cases/{case_id}/brief')
    def case_brief(case_id:str):
        state.detail(case_id)
        return BatchStore(state).brief(case_id)

    @app.get('/api/v1/cases/{case_id}/research-follow-up')
    def case_follow_up(case_id:str):
        return research_follow_up(state,case_id)

    @app.get('/api/v1/cases/{case_id}/pre-outreach-review')
    def case_pre_outreach_review(case_id:str):
        return pre_outreach_review(state,case_id)

    @app.post('/api/v1/cases/{case_id}/research-follow-up/execute')
    def execute_follow_up(case_id:str,request:ResearchExecutionInput):
        return execute_research_intent(state,case_id,request.model_dump(mode='json'))

    @app.get('/api/v1/mandates/{mandate_id}/reference')
    def mandate_reference(mandate_id:str):
        state.mandate(mandate_id)
        ref=state.reference_material
        if ref is None:raise ServiceError('not_found','No pinned mandate reference is configured',404)
        return {'mandate_id':mandate_id,'document_path':ref.document_path,'document_version':ref.document_version,'document_sha256':ref.document_sha256,'document_text':ref.document_text,'qualification_policy_approved':False,'authority':'Full canonical source reference; the short mandate thesis_text is a run brief, not the entire mandate or an approved normalized qualification policy.'}

    @app.post("/api/v1/mandates", response_model=Mandate, status_code=201)
    def create_mandate(request: CreateMandate):
        return state.create_mandate(request)

    @app.get("/api/v1/mandates/{mandate_id}", response_model=Mandate)
    def mandate(mandate_id: str):
        return state.mandate(mandate_id)

    @app.post("/api/v1/mandates/{mandate_id}/run", response_model=Task, status_code=202)
    def run(mandate_id: str, request: Request):
        mandate = state.mandate(mandate_id)
        if settings.provider_mode == "fixture" and any(case.data_mode != "synthetic" for case in state.cases(mandate_id)):
            raise ServiceError("invalid_transition", "This mandate contains genuine research. Fixture discovery cannot rerun it; use an explicitly reviewed live branch. Existing cases/history were preserved.", 409)
        provider.ensure_available(mandate)  # No task or network call before scoped validation.
        task, created = state.enqueue_run(mandate_id)
        if created:
            request.app.state.runner.submit(task.id)
        return task

    @app.get("/api/v1/mandates/{mandate_id}/cases", response_model=CaseList)
    def cases(mandate_id: str):
        return CaseList(items=state.cases(mandate_id))

    @app.get("/api/v1/mandates/{mandate_id}/discovery")
    def discovery_coverage(mandate_id: str):
        state.mandate(mandate_id)
        return DiscoveryStore(state).coverage(mandate_id)

    @app.get("/api/v1/cases/{case_id}", response_model=CaseDetail)
    def case(case_id: str):
        return state.detail(case_id)

    @app.post("/api/v1/cases/{case_id}/qualification-review", response_model=CaseDetail)
    def qualification_review(case_id: str, request: QualificationReviewInput):
        return AgentAssessmentStore(state).review(case_id, request)

    @app.get("/api/v1/cases/{case_id}/research-graph")
    def research_graph(case_id: str):
        return saved_research_graph(state, case_id)

    @app.get("/api/v1/cases/{case_id}/scout-result")
    def case_scout_result(case_id: str):
        return scout_result(state, case_id)

    @app.get("/api/v1/cases/{case_id}/evaluations", response_model=EvaluationList)
    def evaluations(case_id: str):
        return EvaluationList(items=state.detail(case_id).evaluations)

    @app.post("/api/v1/cases/{case_id}/signals", response_model=CaseDetail)
    def signal(case_id: str, request: SignalInput):
        return assessments.replay_signal(case_id, request, catalog)

    @app.get("/api/v1/tasks/{task_id}", response_model=Task)
    def task(task_id: str):
        return state.task(task_id)

    @app.get("/api/v1/fixtures/signals")
    def fixture_signals():
        """Additive fixture helper. Frontend may match by canonical_domain."""
        return {"data_mode": "synthetic", "items": [
            {"company_name": company["company_name"], "canonical_domain": company["canonical_domain"], "label": replay["label"], "signal": replay["input"]}
            for company in catalog.companies.values() for replay in company.get("signals", [])
        ]}

    return app


app = create_app()
