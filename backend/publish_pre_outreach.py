"""Explicit free publication of the pinned, source-authored nine-case overlay."""
import json
from pathlib import Path
from collections import Counter
from backend.scout_batch import environment
from backend.app.pre_outreach import active_sources,accept_review,pre_outreach_review
from backend.app.agent_bridge import comparison_packet
from backend.app.settings import APP_ROOT
from agents.models import MatcherResult
from agents.pre_outreach import PreOutreachOverlay,PreOutreachGuidance,build_pre_outreach_review

def adapt(entry,context,sources):
    people=entry['person_actionability'];bound=people.get('bound_people',[])
    person_ids=[p['person_id'] for p in bound]
    person_evidence=list(dict.fromkeys(eid for p in bound for role in p['roles'] for eid in role['evidence_ids']))
    status='unknown' if not person_ids else ('source_attributed_current' if people['status'].startswith('named_current') else 'historical_or_uncertain')
    blocker=entry.get('decisive_blocker');notes=[];questions=[]
    for q in entry['call_questions']:
        if q.get('text'):questions.append(q)
        elif blocker:
            questions.append({'text':blocker['text'],'evidence_ids':blocker['evidence_ids']})
            notes.append('Null source question adapted from the same entry decisive_blocker text and its own evidence IDs; pinned source bytes unchanged.')
    mapping={'identity_and_scope':'identity_scope','concrete_product_program_or_problem':'concrete_product_program_problem','useful_conversation_reason':'useful_conversation_reason'}
    minimum={target:{'status':'supported' if entry['minimum_basis'][origin]['supported'] else 'unresolved','text':entry['minimum_basis'][origin]['text'],'evidence_ids':entry['minimum_basis'][origin]['evidence_ids']} for target,origin in mapping.items()}
    guidance=PreOutreachGuidance(source_path=sources['case_guidance']['path'],source_sha256=sources['case_guidance']['sha256'],version=sources['case_guidance']['version'],entry_id=entry['case_id']+':pre-outreach:0.1',input_ref=entry['input_ref'],assessment_ref=entry['assessment_ref'],author='Investment-thesis owner, human-authorized stage-calibration interpretation',suggested_category=entry['category'],rationale=entry['rationale'],minimum=minimum,contrary_facts=[{**c,'effect':'limits_claim'} for c in entry['contrary_facts']],call_questions=questions,pre_intro_blocker={'kind':'current_operator_or_status','text':blocker['text'],'evidence_ids':blocker['evidence_ids'],'what_to_resolve':blocker['text'],'decision_consequence':entry.get('what_would_change_category','Resolve this specific currentness issue before recommending a current-company introduction.')} if blocker else None,future_merit_trigger=None,relevant_person={'status':status,'person_ids':person_ids,'evidence_ids':person_evidence,'explanation':people['limits']},contact_route={'status':'not_established','route_kind':'unknown','route_ref':None,'person_id':None,'evidence_ids':[],'explanation':entry['contact_actionability']['limits']})
    return guidance,notes

def publish():
    _,state,_=environment();sources=active_sources();guidance_source=json.loads((APP_ROOT/sources['case_guidance']['path']).read_text(encoding='utf-8-sig'));output=[]
    for entry in guidance_source['cases']:
        context=state.load_assessment_context(entry['case_id']);packet=comparison_packet(context,output_tokens=0)
        with state.connection() as db:row=db.execute('SELECT id,payload FROM semantic_assessments WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(entry['case_id'],)).fetchone()
        assert row['id']==entry['assessment_ref'] and context.case.version==entry['case_version'] and packet.ref.model_dump(mode='json')==entry['input_ref']
        overlay=PreOutreachOverlay(id=sources['policy_overlay']['id'],version=sources['policy_overlay']['version'],source_path=sources['policy_overlay']['path'],source_sha256=sources['policy_overlay']['sha256'],base_reference_sha256=context.reference_material.document_sha256,authorization_ref=sources['authorization_ref'])
        guidance,notes=adapt(entry,context,sources)
        review=build_pre_outreach_review(packet,MatcherResult.model_validate(json.loads(row['payload'])['result']),assessment_ref=row['id'],overlay=overlay,guidance=guidance,current_ref=packet.ref)
        record_id=accept_review(state,context,row['id'],review.model_dump(mode='json'),sources=sources)
        projection=pre_outreach_review(state,entry['case_id']);assert projection['status']=='ready'
        output.append({'domain':entry['domain'],'case_id':entry['case_id'],'review_id':record_id,'category':review.category,'person_status':review.relevant_person.status,'contact_route_status':review.contact_route.status,'adapter_notes':notes,'projection':projection})
    folder=APP_ROOT/'backend/work/pre-outreach';folder.mkdir(exist_ok=True);report={'sources':sources,'counts':dict(Counter(x['category'] for x in output)),'cases':output,'new_provider_or_model_calls':0,'old_assessments_or_statuses_changed':False}
    (folder/'published-reviews.json').write_text(json.dumps(report,indent=2));print(json.dumps({'published':len(output),'counts':report['counts'],'new_calls':0}))

if __name__=='__main__':publish()
