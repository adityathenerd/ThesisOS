"""Pure save/projection after the one genuine matcher call; no paid calls."""
import json
from agents.models import MatcherResult
from agents.research_graph import ResearchGraph,to_mermaid
from backend.app.assessments import load_reference_material
from backend.app.research_graph import record_research_decision,saved_research_graph,scout_result
from backend.app.settings import APP_ROOT,Settings
from backend.app.state import StateService


def run():
    folder=APP_ROOT/'backend/work/first-scout'
    receipt=json.loads((folder/'matcher.json').read_text())
    result=MatcherResult.model_validate(receipt['result'])
    if receipt['status']!='stored_genuine_result' or result.assessment is None:raise RuntimeError('No genuine rich matcher result available')
    settings=Settings.from_environment();reference=load_reference_material(APP_ROOT,settings.reference_source_config)
    state=StateService(settings.sqlite_path(),reference);state.initialize()
    # Explicit application of the actual monitor next-action judgment, not a
    # keyword heuristic or an accepted investment/qualification transition.
    if result.assessment.proposed_disposition!='monitor':raise RuntimeError('Review actual next-action timing before finalizing another disposition')
    decision=record_research_decision(state,receipt['case_id'],receipt['assessment_id'],action_timing='future',decision_consequence='Inspectable evidence of a reusable differentiated workflow/product and attributable contribution could reopen targeted H-track investigation; no automatic qualification follows.',future_trigger=result.assessment.stop_or_reopen_condition)
    graph=ResearchGraph.model_validate(saved_research_graph(state,receipt['case_id']))
    (folder/'research-graph.json').write_text(graph.model_dump_json(indent=2),encoding='utf-8')
    (folder/'research-graph.mmd').write_text(to_mermaid(graph),encoding='utf-8')
    projection=scout_result(state,receipt['case_id'])
    (folder/'scout-result.json').write_text(json.dumps(projection,indent=2),encoding='utf-8')
    summary={'status':'saved_real_scout_graph_and_genuine_monitor_recommendation','case_id':receipt['case_id'],'assessment_id':receipt['assessment_id'],'graph_id':graph.graph_id,'case_version':graph.snapshot_ref.case_version,'nodes':len(graph.nodes),'edges':len(graph.edges),'source_groups':len(graph.sources),'open_questions':len(graph.open_questions),'matcher_interpretations':len(graph.matcher_interpretations),'research_decision':decision['decision'],'future_trigger':decision['future_trigger'],'case_route':'/api/v1/cases/'+receipt['case_id'],'graph_route':'/api/v1/cases/'+receipt['case_id']+'/research-graph','result_route':'/api/v1/cases/'+receipt['case_id']+'/scout-result','qualification_accepted':False,'new_paid_calls':0}
    (folder/'milestone.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':run()
