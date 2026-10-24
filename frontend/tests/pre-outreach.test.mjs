import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {readPreOutreach,currentPreOutreach,conversationView} from '../src/pre-outreach.ts';
import {referenceHash,localReferenceMeta} from '../src/mandate-reference.ts';
import {preOutreachPolicyMeta} from '../src/pre-outreach-policy.ts';
const ref={case_id:'case',case_version:3,thesis_version:1,policy_version:1,evidence_hash:'saved-evidence'};
const detail=()=>({id:'case',version:3,evidence:[{id:'source'}],people:[],agent_assessments:[{id:'assessment',input_current:true,expected_case_version:3,created_at:'2026-10-24T10:00:00Z',structured_result:{ref}}]});
function ready(){return {status:'ready',case_id:'case',case_version:3,assessment_id:'assessment',review_id:'review',stale_reasons:[],qualification_accepted:false,authority:'Saved-evidence stage interpretation',sources:{active:true,policy_overlay:{sha256:'a'.repeat(64)},case_guidance:{sha256:'b'.repeat(64)}},review:{schema_version:'0.1',input_ref:ref,assessment_ref:'assessment',assessment_prompt_version:'0.3',overlay:{id:'overlay',version:'0.1',source_sha256:'a'.repeat(64),base_reference_sha256:localReferenceMeta.document_sha256},guidance_source_sha256:'b'.repeat(64),category:'outreach_candidate',rationale:{text:'A sourced reason for an introductory conversation.',evidence_ids:['source']},minimum:{identity_and_scope:{status:'supported',text:'Source-described identity.',evidence_ids:['source']}},contrary_facts:[],call_questions:[{text:'Who built and currently operates it?',evidence_ids:['source']}],relevant_person:{status:'unknown',person_ids:[],evidence_ids:[],explanation:'No individual builder is identified.'},contact_route:{status:'not_established',route_kind:'unknown',route_ref:null,person_id:null,evidence_ids:[],explanation:'No personal route is established.'},pre_intro_blocker:null,future_merit_trigger:null,next_step:'resolve_person_or_route_for_human_review',guard_notes:[],provenance:'human-authorized_stage_calibration_interpretation_using_existing_evidence',newly_executed_model:false,changes_formal_readiness:false,changes_qualification:false,sending_authorized:false}};}
test('reported intro merit remains separate from unknown person/contact completeness',()=>{
 const d=detail(),state=readPreOutreach(ready(),d),view=conversationView(state.review,d);assert.equal(currentPreOutreach(state,d),true);assert.equal(state.review.category,'outreach_candidate');assert.equal(view.person.label,'Relevant person not identified');assert.equal(view.contact.label,'Contact route not established');assert.equal(state.review.sending_authorized,false);
});
test('stale assessments, evidence snapshots and inactive or changed source overlays are refused',()=>{
 const d=detail(),data=ready();data.review.input_ref={...ref,evidence_hash:'old'};assert.equal(readPreOutreach(data,d).status,'stale');
 const newAssessment={...d,agent_assessments:[{...d.agent_assessments[0],id:'new'}]};assert.equal(readPreOutreach(ready(),newAssessment).status,'stale');
 const changed=ready();changed.sources.policy_overlay.sha256='c'.repeat(64);assert.throws(()=>readPreOutreach(changed,d),/binding/);
 const inactive=ready();inactive.sources.active=false;assert.throws(()=>readPreOutreach(inactive,d),/binding/);
 assert.equal(readPreOutreach({...ready(),status:'stale',stale_reasons:['policy changed']},d).review,null);
});
test('unsupported citations or qualification/sending claims cannot become a stage review',()=>{
 const bad=ready();bad.review.call_questions[0].evidence_ids=['foreign'];assert.throws(()=>readPreOutreach(bad,detail()),/unavailable saved source/);
 const send=ready();send.review.sending_authorized=true;assert.throws(()=>readPreOutreach(send,detail()),/authority/);
});
test('the complete additive policy snapshot preserves its published identity',async()=>{
 const text=fs.readFileSync(new URL('../src/reference/pre-outreach-overlay-v0.1.md',import.meta.url),'utf8');assert.equal(await referenceHash(text),preOutreachPolicyMeta.sha256);assert.match(text,/private demo/i);assert.match(text,/research_first/);assert.match(text,/formal partner-review/i);
});
