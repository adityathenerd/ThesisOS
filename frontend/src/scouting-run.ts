export interface ScoutingRun{
 id:string;status:'queued'|'running'|'stopping'|'stopped'|'completed'|'failed'|'interrupted';created_at:string;updated_at:string;started_at?:string;deadline:string;finished_at?:string;
 limits:{max_new_cases:number;max_provider_requests:number;max_credits:number;max_model_assessments:number};max_concurrent:number;
 attempts:{intent:string;kind:'provider'|'model'|'public';status:string;quoted_microcredits:number;actual_microcredits:number|null;started_at:string;finished_at?:string;request?:Record<string,unknown>}[];
 candidates:{key:string;company_name:string;domain:string|null;track_hypothesis:string;rank:number;stage:string;case_id?:string;assessment_id?:string;reason?:string;research_state?:string;completion_scope?:string;source_attempts?:Record<string,unknown>[];remaining_public_attempts?:number;execution_input_ref?:{case_version:number}}[];
 completed_case_ids:string[];mandate_id:string|null;task_id:string|null;current_operation:string|null;stop_requested:boolean;stop_reason:string|null;
}
export const activeScoutingRun=(r:ScoutingRun|null|undefined)=>!!r&&['queued','running','stopping'].includes(r.status);
export function scoutingUsage(r:ScoutingRun){
 const provider=r.attempts.filter(a=>a.kind==='provider');
 return {providerAttempts:provider.length,modelAttempts:r.attempts.filter(a=>a.kind==='model').length,confirmedCredits:provider.reduce((sum,a)=>sum+(a.actual_microcredits??0),0)/1e6,reservedCredits:provider.filter(a=>a.actual_microcredits===null).reduce((sum,a)=>sum+a.quoted_microcredits,0)/1e6,unknownReceipts:provider.filter(a=>a.actual_microcredits===null).length,newCases:'stage_kind' in r&&r.stage_kind==='bounded_post_intake_followthrough'?0:new Set(r.candidates.flatMap(c=>c.case_id?[c.case_id]:[])).size,casesInScope:new Set(r.candidates.flatMap(c=>c.case_id?[c.case_id]:[])).size,completeCases:new Set(r.completed_case_ids).size};
}
export function readScoutingRun(input:unknown):ScoutingRun{
 if(!input||typeof input!=='object')throw Error('Scouting run is not reported.');
 const r=input as ScoutingRun;
 if(typeof r.id!=='string'||!['queued','running','stopping','stopped','completed','failed','interrupted'].includes(r.status)||!Number.isFinite(Date.parse(r.deadline))||!r.limits||!Array.isArray(r.attempts)||!Array.isArray(r.candidates)||!Array.isArray(r.completed_case_ids)||r.attempts.some(a=>!['provider','model','public'].includes(a.kind)||typeof a.quoted_microcredits!=='number'||(a.actual_microcredits!==null&&typeof a.actual_microcredits!=='number')))throw Error('Unsupported scouting run status.');
 return r;
}

export interface FollowThroughStage extends ScoutingRun{parent_run_id:string;stage_kind:'bounded_post_intake_followthrough';limits:ScoutingRun['limits']&{public_urls_per_case:number}}
export function readFollowThroughStage(input:unknown,parentId:string):FollowThroughStage{const stage=readScoutingRun(input) as FollowThroughStage;if(stage.parent_run_id!==parentId||stage.stage_kind!=='bounded_post_intake_followthrough'||stage.limits.max_new_cases!==0||typeof stage.limits.public_urls_per_case!=='number')throw Error('Follow-through stage does not match the saved intake run.');return stage;}
export type CaseFollowThrough={stage:FollowThroughStage;candidate:ScoutingRun['candidates'][number]};
export function caseFollowThrough(stages:Record<string,FollowThroughStage>,caseId:string):CaseFollowThrough|null{const ordered=Object.values(stages).sort((a,b)=>Number(activeScoutingRun(b))-Number(activeScoutingRun(a))||b.updated_at.localeCompare(a.updated_at));for(const stage of ordered){const candidate=stage.candidates.find(c=>c.case_id===caseId);if(candidate)return{stage,candidate};}return null;}
export function followThroughLabel(value:CaseFollowThrough){const{stage,candidate}=value;if(candidate.stage==='queued'&&!activeScoutingRun(stage))return 'Enrichment stopped before attempt';return ({queued:'Enrichment queued',directed_research:'Researching',reassessing:'Reassessing',human_handoff_no_material_delta:'Human handoff',waiting_external_tool_receipt:'Waiting for tool receipt',complete:candidate.research_state==='human_research_required'?'Human handoff':candidate.research_state==='ready_for_human_review'?'Ready for human review':candidate.research_state==='monitor'?'Monitor':'Follow-through assessed'} as Record<string,string>)[candidate.stage]??candidate.stage.replaceAll('_',' ');}
export function caseFollowThroughActive(value:CaseFollowThrough|null){return !!value&&activeScoutingRun(value.stage)&&['queued','directed_research','reassessing','waiting_external_tool_receipt'].includes(value.candidate.stage);}

export function publicPageAttempts(stage:ScoutingRun){return stage.attempts.filter(a=>a.kind==='public').reduce((sum,a)=>{const direct=a.request?.public_page_attempts,external=a.request?.external;const nested=external&&typeof external==='object'?(external as Record<string,unknown>).public_page_attempts:undefined;return sum+(typeof direct==='number'?direct:typeof nested==='number'?nested:1);},0);}
