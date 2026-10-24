"""Serve the agent-owned pure graph schema from accepted saved research."""
import json
from agents.models import CaseContext,MatcherResult
from agents.research_graph import AssertionSpec,EntitySpec,ObservationGraphMetadata,ResearchQuestion,ResearchDecisionSpec,ProviderResponseGroup,TopicInterestSpec,build_research_graph,decision_from_matcher
from .agent_bridge import comparison_packet
from .errors import ServiceError
from .state import now,uid


def record_research_decision(state,case_id,assessment_id,*,action_timing=None,decision_consequence,future_trigger=None):
    with state.connection(write=True) as db:
        context=state._assessment_context(db,case_id)
        row=db.execute('SELECT payload FROM semantic_assessments WHERE id=? AND case_id=?',(assessment_id,case_id)).fetchone()
        if not row:raise ServiceError('not_found','Assessment not found',404)
        data=json.loads(row[0])
        if data['backend_versions']!=context.versions.model_dump(mode='json'):raise ServiceError('stale_version','Research decision requires current assessment inputs',409)
        result=MatcherResult.model_validate(data['result'])
        decision=decision_from_matcher(result,assessment_ref=assessment_id,action_timing=action_timing,decision_consequence=decision_consequence,future_trigger=future_trigger)
        payload={'spec':decision.model_dump(mode='json'),'backend_versions':data['backend_versions'],'decision_source':'Explicit timing classification of the genuine matcher next action; not qualification','created_at':now()}
        old=db.execute('SELECT payload FROM research_decisions WHERE assessment_id=?',(assessment_id,)).fetchone()
        if old:return json.loads(old[0])['spec']
        db.execute('INSERT INTO research_decisions VALUES (?,?,?,?,?)',(uid('decision'),case_id,assessment_id,json.dumps(payload),now()))
        state._event(db,case_id,'research_next_action_recorded',f"Research next-action recommendation: {decision.decision}; assessment {assessment_id}. No human qualification or outreach accepted.",decision.evidence_ids,data_mode=context.case.data_mode)
        return decision.model_dump(mode='json')


def saved_research_graph(state,case_id):
    with state.connection(snapshot=True) as db:
        context=state._assessment_context(db,case_id)
        record=db.execute('SELECT id,payload FROM semantic_assessments WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)).fetchone()
        decision_row=db.execute('SELECT assessment_id,payload FROM research_decisions WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)).fetchone()
    data=json.loads(record['payload']) if record else None
    current=data is not None and data['backend_versions']==context.versions.model_dump(mode='json')
    packet=CaseContext.model_validate(data['agent_context']) if current else comparison_packet(context,output_tokens=0)
    result=MatcherResult.model_validate(data['result']) if current and data['result'].get('assessment') is not None else None
    decision_data=json.loads(decision_row['payload']) if decision_row else None
    decision=ResearchDecisionSpec.model_validate(decision_data['spec']) if result and decision_row and decision_row['assessment_id']==record['id'] and decision_data['backend_versions']==context.versions.model_dump(mode='json') else None
    research=context.research_context or {}
    graph=build_research_graph(packet,generated_at=now(),observation_metadata=[ObservationGraphMetadata.model_validate(x) for x in research.get('observation_metadata',[])],entities=[EntitySpec.model_validate(x) for x in research.get('entities',[])],assertions=[AssertionSpec.model_validate(x) for x in research.get('assertions',[])],questions=[ResearchQuestion.model_validate(x) for x in research.get('questions',[])],matcher_result=result,assessment_ref=record['id'] if result else None,decision=decision,limitations=research.get('limitations',[]),provider_response_groups=[ProviderResponseGroup.model_validate(x) for x in research.get('provider_response_groups',[])],topic_interests=[TopicInterestSpec.model_validate(x) for x in research.get('topic_interests',[])],include_ecosystem_coverage=research.get('include_ecosystem_coverage',False))
    with state.connection(write=True) as db:
        actual=state._assessment_context(db,case_id)
        latest=db.execute('SELECT id FROM semantic_assessments WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)).fetchone()
        if actual.versions!=context.versions or (latest[0] if latest else None)!=(record['id'] if record else None):raise ServiceError('stale_version','Research context changed during projection; reload graph',409,True)
        db.execute('INSERT OR IGNORE INTO research_graph_snapshots VALUES (?,?,?,?)',(graph.graph_id,case_id,graph.model_dump_json(),graph.generated_at))
        return json.loads(db.execute('SELECT payload FROM research_graph_snapshots WHERE id=?',(graph.graph_id,)).fetchone()[0])


def scout_result(state,case_id):
    with state.connection(snapshot=True) as db:
        detail=state._detail(db,case_id)
        row=db.execute('SELECT assessment_id,payload FROM research_decisions WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)).fetchone()
        context=state._assessment_context(db,case_id)
    payload=json.loads(row['payload']) if row else None
    current=payload is not None and payload['backend_versions']==context.versions.model_dump(mode='json')
    from .batch import BatchStore
    try: brief=BatchStore(state).brief(case_id)['brief']
    except ServiceError: brief=None
    return {'case_id':case_id,'case_version':detail.version,'company_name':detail.company_name,'assessment_id':row['assessment_id'] if row else None,'research_decision':payload['spec'] if current else None,'decision_current':current,'agent_assessments':[a.model_dump(mode='json') for a in detail.agent_assessments],'case_brief':brief,'qualification_accepted':any(r.current and r.decision=='approve' for r in detail.qualification_reviews),'novelty_status':'unknown','graph_route':f'/api/v1/cases/{case_id}/research-graph'}
