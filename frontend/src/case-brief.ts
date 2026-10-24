import type {CaseDetail} from './types';
import {editorialBriefs} from './reference/editorial-briefs.ts';
import {refineSavedBrief} from './reference/brief-refinements.ts';

export interface BriefClaim{text:string;evidence_ids:string[]}
export interface FounderSignal{person:string;contribution:string;relevance:string;source_strength:string;limitation:string;evidence_ids:string[]}
export interface CaseBrief{case_id:string;case_version:number;assessment_id:string;business:BriefClaim;decision:'pursue'|'monitor';recommendation:BriefClaim;reasons:BriefClaim[];founder_signals:FounderSignal[];founder_unknown:string|null;decisive_doubt:BriefClaim;next_action:BriefClaim;material_caveats:string[];operational_limitations?:string[];origin:'editorial_saved_evidence'|'saved_agent_brief'}
export type BriefState={status:'available';brief:CaseBrief}|{status:'missing'|'stale'|'invalid';message:string};

export function validateBrief(brief:CaseBrief,detail:CaseDetail):BriefState{
 if(brief.case_id!==detail.id||brief.case_version!==detail.version)return{status:'stale',message:'This brief belongs to an earlier case version. A current summary is needed.'};
 const record=detail.agent_assessments?.find(item=>item.id===brief.assessment_id);
 if(!record||!record.input_current||record.expected_case_version!==detail.version)return{status:'stale',message:'The concise brief is not bound to a current saved assessment.'};
 const latest=detail.agent_assessments?.filter(item=>item.input_current).sort((a,b)=>a.created_at.localeCompare(b.created_at)).at(-1);
 if(latest?.id!==brief.assessment_id)return{status:'stale',message:'A newer assessment is available. Its brief has not been saved yet.'};
 if(!['pursue','monitor'].includes(brief.decision)||!Array.isArray(brief.reasons)||brief.reasons.length>2||!Array.isArray(brief.founder_signals))return{status:'invalid',message:'The saved brief has an unsupported shape.'};
 const ids=new Set(detail.evidence.map(item=>item.id));
 const claims=[brief.business,brief.recommendation,...brief.reasons,brief.decisive_doubt,brief.next_action];
 if(claims.some(claim=>!claim||typeof claim.text!=='string'||!claim.text.trim()||!Array.isArray(claim.evidence_ids)||claim.evidence_ids.some(id=>!ids.has(id)))||brief.reasons.some(claim=>!claim.evidence_ids.length))return{status:'invalid',message:'A concise claim has an invalid link to the saved evidence.'};
 if(brief.founder_signals.some(signal=>!signal.person||!signal.contribution||!signal.relevance||!signal.source_strength||!signal.limitation||!Array.isArray(signal.evidence_ids)||!signal.evidence_ids.length||signal.evidence_ids.some(id=>!ids.has(id))))return{status:'invalid',message:'Founder work needs a named person, attribution, relevance, limits and saved sources.'};
 return{status:'available',brief};
}

export function resolveBrief(detail:CaseDetail):BriefState{
 const record=detail.agent_assessments?.filter(item=>!!item.structured_result.assessment?.case_brief).sort((a,b)=>a.created_at.localeCompare(b.created_at)).at(-1);
 if(record){
  try{
   const wire=record.structured_result.assessment!.case_brief!,ref=record.structured_result.ref;
   if(!ref||ref.case_id!==detail.id||ref.case_version!==detail.version)return{status:'stale',message:'The saved brief snapshot differs from this case.'};
   if(wire.research_posture==='monitor'&&!wire.future_trigger?.trim())return{status:'invalid',message:'A monitor recommendation needs a specific future trigger.'};
   const strength={first_party_claim:'Company-reported',inspectable_work:'Inspectable work',independent_report:'Independent report',mixed:'Mixed source basis'};
   const brief:CaseBrief={case_id:detail.id,case_version:ref.case_version,assessment_id:record.id,origin:'saved_agent_brief',business:wire.company_description,decision:wire.research_posture,recommendation:wire.main_reason,reasons:wire.strongest_facts,founder_signals:wire.founder_signals.map(signal=>({person:detail.people?.find(person=>person.id===signal.person_id&&person.case_version===detail.version)?.name??'Contributor name not available',contribution:signal.contribution,relevance:signal.relevance,evidence_ids:signal.evidence_ids,source_strength:strength[signal.source_strength]??'Source strength unknown',limitation:signal.source_strength==='first_party_claim'?'Company attribution; not independent verification.':signal.source_strength==='inspectable_work'?'Inspectable work supports this contribution; it does not establish all outcomes.':'Attribution and its limits remain in the linked evidence.'})),founder_unknown:wire.founder_unknowns.join(' ')||null,decisive_doubt:wire.decisive_doubt,next_action:{text:wire.research_posture==='monitor'?wire.future_trigger!:wire.next_action,evidence_ids:[]},material_caveats:[],operational_limitations:wire.operational_limitations};
   return validateBrief(refineSavedBrief(brief,ref),detail);
  }catch{return{status:'invalid',message:'The saved brief could not be read. Its full assessment remains available.'};}
 }
 const editorial=editorialBriefs.find(item=>item.case_id===detail.id);
 if(editorial)return validateBrief(editorial,detail);
 return{status:'missing',message:'A concise company and founder brief has not been saved for this case yet.'};
}
