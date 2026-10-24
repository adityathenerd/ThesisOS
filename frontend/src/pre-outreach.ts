import type {CaseDetail} from './types';
import type {VersionRef} from './research-graph';
import type {ConversationReviewView} from './ConversationReview';
import {localReferenceMeta} from './mandate-reference.ts';
export type ConversationCategory='outreach_candidate'|'research_first'|'monitor'|'outside_scope';
export interface CalibrationClaim{text:string;evidence_ids:string[]}
export interface PreOutreachReview{
 schema_version:'0.1';input_ref:VersionRef;assessment_ref:string;assessment_prompt_version:string;
 overlay:{id:string;version:string;source_path:string;source_sha256:string;base_reference_sha256:string;authorization_ref:string};
 guidance_source_path:string;guidance_source_sha256:string;guidance_version:string;guidance_entry_id:string;author:string;
 category:ConversationCategory;suggested_category:ConversationCategory;rationale:CalibrationClaim;
 minimum:Record<string,CalibrationClaim&{status:string}>;contrary_facts:(CalibrationClaim&{effect:string})[];call_questions:CalibrationClaim[];
 pre_intro_blocker:(CalibrationClaim&{kind:string;what_to_resolve:string;decision_consequence:string})|null;
 future_merit_trigger:CalibrationClaim|null;
 relevant_person:{status:'source_attributed_current'|'historical_or_uncertain'|'unknown';person_ids:string[];evidence_ids:string[];explanation:string};
 contact_route:{status:'source_supported_route'|'not_established'|'human_confirmation_needed';route_kind:string;route_ref:string|null;person_id:string|null;evidence_ids:string[];explanation:string};
 next_step:string;guard_notes:string[];provenance:'human-authorized_stage_calibration_interpretation_using_existing_evidence';newly_executed_model:false;changes_formal_readiness:false;changes_qualification:false;sending_authorized:false;
}
export interface PreOutreachState{status:'ready'|'stale'|'unavailable';case_id:string;case_version:number;assessment_id:string|null;review_id:string|null;review:PreOutreachReview|null;message:string;authority:string;sources:Record<string,unknown>|null}
const categories=['outreach_candidate','research_first','monitor','outside_scope'];
export const conversationLabel=(category:ConversationCategory)=>({outreach_candidate:'Intro conversation candidate',research_first:'Research first',monitor:'Monitor',outside_scope:'Outside scope'})[category];
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const hash=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const sameRef=(a:VersionRef,b:VersionRef)=>['case_id','case_version','thesis_version','policy_version','evidence_hash'].every(key=>a[key as keyof VersionRef]===b[key as keyof VersionRef]);
export function currentPreOutreach(state:PreOutreachState|undefined|null,detail:CaseDetail|undefined|null):state is PreOutreachState&{review:PreOutreachReview}{
 if(!state||!detail||state.status!=='ready'||!state.review||state.case_id!==detail.id||state.case_version!==detail.version)return false;
 const assessment=detail.agent_assessments?.filter(a=>a.input_current&&a.expected_case_version===detail.version).sort((a,b)=>a.created_at.localeCompare(b.created_at)).at(-1);
 return !!assessment&&!!assessment.structured_result.ref&&assessment.id===state.assessment_id&&assessment.id===state.review.assessment_ref&&sameRef(state.review.input_ref,assessment.structured_result.ref);
}
export function readPreOutreach(input:unknown,detail:CaseDetail):PreOutreachState{
 if(!object(input)||!['ready','stale','unavailable'].includes(String(input.status))||input.case_id!==detail.id||input.case_version!==detail.version)throw Error('Pre-outreach review has no matching case binding.');
 const base:PreOutreachState={status:input.status as PreOutreachState['status'],case_id:detail.id,case_version:detail.version,assessment_id:typeof input.assessment_id==='string'?input.assessment_id:null,review_id:typeof input.review_id==='string'?input.review_id:null,review:null,message:Array.isArray(input.stale_reasons)?input.stale_reasons.join(' · '):'',authority:typeof input.authority==='string'?input.authority:'',sources:object(input.sources)?input.sources:null};
 if(base.status!=='ready')return base;
 const r=input.review;
 if(!object(r)||r.schema_version!=='0.1'||!categories.includes(String(r.category))||typeof r.assessment_ref!=='string'||!object(r.input_ref)||!object(r.overlay)||!object(r.rationale)||typeof r.rationale.text!=='string'||!Array.isArray(r.call_questions)||r.call_questions.length<1||r.call_questions.length>2||!r.call_questions.every(q=>object(q)&&typeof q.text==='string')||!Array.isArray(r.contrary_facts)||!object(r.minimum)||!object(r.relevant_person)||!object(r.contact_route))throw Error('Unsupported pre-outreach review shape.');
 if(input.qualification_accepted!==false||r.provenance!=='human-authorized_stage_calibration_interpretation_using_existing_evidence'||['newly_executed_model','changes_formal_readiness','changes_qualification','sending_authorized'].some(key=>r[key]!==false))throw Error('Pre-outreach authority differs from a saved-evidence stage interpretation.');
 if(!['source_attributed_current','historical_or_uncertain','unknown'].includes(String(r.relevant_person.status))||!['source_supported_route','not_established','human_confirmation_needed'].includes(String(r.contact_route.status))||typeof r.relevant_person.explanation!=='string'||typeof r.contact_route.explanation!=='string'||!Array.isArray(r.relevant_person.person_ids))throw Error('Unknown contact-preparation status.');
 const policy=base.sources?.policy_overlay,guidance=base.sources?.case_guidance;
 if(base.sources?.active!==true||!object(policy)||!object(guidance)||!hash(r.overlay.source_sha256)||!hash(r.guidance_source_sha256)||r.overlay.source_sha256!==policy.sha256||r.guidance_source_sha256!==guidance.sha256||r.overlay.base_reference_sha256!==localReferenceMeta.document_sha256)throw Error('Pre-outreach source policy/guidance binding is not confirmed.');
 const evidence=new Set(detail.evidence.map(e=>e.id));
 function citations(value:unknown){if(Array.isArray(value)){value.forEach(citations);return}if(!object(value))return;for(const [key,v] of Object.entries(value)){if(key==='evidence_ids'&&(!Array.isArray(v)||v.some(id=>typeof id!=='string'||!evidence.has(id))))throw Error('Pre-outreach review cites an unavailable saved source.');citations(v);}}
 citations(r);
 const state={...base,review:r as unknown as PreOutreachReview};
 if(!currentPreOutreach(state,detail))return {...base,status:'stale',message:'The pre-outreach review does not match the current saved assessment and evidence snapshot.'};
 if(base.message)throw Error('A current pre-outreach review also reported stale reasons.');
 return state;
}
export function conversationView(review:PreOutreachReview,detail:CaseDetail):ConversationReviewView{
 const personLabels={source_attributed_current:'Current role is source-attributed',historical_or_uncertain:'Current role needs confirmation',unknown:'Relevant person not identified'};
 const routeLabels={source_supported_route:'Saved route for human review',not_established:'Contact route not established',human_confirmation_needed:'Human confirmation needed'};
 const names=review.relevant_person.person_ids.flatMap(id=>{const person=detail.people?.find(p=>p.id===id&&p.case_version===detail.version);return person?[person.name]:[]});
 return {label:conversationLabel(review.category),tone:({outreach_candidate:'candidate',research_first:'research',monitor:'monitor',outside_scope:'outside'} as const)[review.category],rationale:review.rationale,counterpoint:review.pre_intro_blocker??review.contrary_facts[0]??review.future_merit_trigger??null,person:{label:names.join(', ')||personLabels[review.relevant_person.status],detail:personLabels[review.relevant_person.status]+'. '+review.relevant_person.explanation},contact:{label:routeLabels[review.contact_route.status],detail:review.contact_route.explanation},questions:review.call_questions.map((q,i)=>({id:`call-question-${i}`,question:q.text,context:null,evidence_ids:q.evidence_ids}))};
}
