"""One meaningful authorized genuine matcher call on the saved first-scout case."""
import json
from time import perf_counter

from backend.app.agent_bridge import AgentAssessmentStore, ScriptedGraphTransport, comparison_packet
from backend.app.assessments import load_reference_material
from backend.app.settings import APP_ROOT, Settings
from backend.app.state import StateService


def run():
    folder=APP_ROOT/'backend/work/first-scout';out=folder/'matcher.json'
    if out.exists():
        data=json.loads(out.read_text());print(json.dumps({'existing_receipt':True,'status':data['status'],'assessment_id':data.get('assessment_id')}));return
    case_id=json.loads((folder/'search.json').read_text())['case_id']
    settings=Settings.from_environment();reference=load_reference_material(APP_ROOT,settings.reference_source_config)
    state=StateService(settings.sqlite_path(),reference);state.initialize()
    context=state.load_assessment_context(case_id);invocation=state.begin_assessment(context)
    packet=comparison_packet(context,output_tokens=6000)
    task=' For this first-scout research task, clearly choose in next_action whether to pursue one useful specific evidence/review action now or monitor for a concrete future trigger; explain the decision consequence and stop/reopen condition. This is research priority, not automatic qualification. Assess the current services-only statement against any reusable-core claim without inventing product proof, founder tenure, YC novelty or a why-now catalyst.'
    packet=packet.model_copy(update={'policy':packet.policy.model_copy(update={'fit_rule':packet.policy.fit_rule+task})})
    receipt={'status':'started','case_id':case_id,'invocation_id':invocation,'qualification_policy_approved':False,'new_model_attempts':1,'new_provider_searches':0,'context':packet.model_dump(mode='json')}
    out.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    transport=ScriptedGraphTransport(timeout_seconds=110,live_authorized=True)
    start=perf_counter()
    try:
        result=transport.invoke(packet)
        receipt.update(metadata=transport.last_metadata,result=result.model_dump(mode='json'))
        assessment_id=AgentAssessmentStore(state).record(context,invocation,packet,result,provenance='compiled_graph_live')
        receipt.update(status='stored_genuine_result',assessment_id=assessment_id,elapsed_seconds=round(perf_counter()-start,3))
    except Exception:
        state.record_assessment_failure(invocation,'agent_integration_failed','Bounded first-scout matcher failed; no automatic retry or qualification accepted.')
        receipt.update(status='failed',elapsed_seconds=round(perf_counter()-start,3),error='Bounded agent integration failed. Raw transport/secret details omitted; no retry.')
    out.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({'status':receipt['status'],'assessment_id':receipt.get('assessment_id'),'metadata':receipt.get('metadata'),'outcome':receipt.get('result',{}).get('outcome'),'proposed_disposition':receipt.get('result',{}).get('assessment',{}).get('proposed_disposition') if receipt.get('result',{}).get('assessment') else None,'next_action':receipt.get('result',{}).get('assessment',{}).get('next_action') if receipt.get('result',{}).get('assessment') else None}))


if __name__=='__main__':run()
