export interface ScoutingRun{
 id:string;status:'queued'|'running'|'stopping'|'stopped'|'completed'|'failed'|'interrupted';created_at:string;updated_at:string;started_at?:string;deadline:string;finished_at?:string;
 limits:{max_new_cases:number;max_provider_requests:number;max_credits:number;max_model_assessments:number};max_concurrent:number;
 attempts:{intent:string;kind:'provider'|'model';status:string;quoted_microcredits:number;actual_microcredits:number|null;started_at:string;finished_at?:string}[];
 candidates:{key:string;company_name:string;domain:string|null;track_hypothesis:string;rank:number;stage:string;case_id?:string;assessment_id?:string;reason?:string}[];
 completed_case_ids:string[];mandate_id:string|null;task_id:string|null;current_operation:string|null;stop_requested:boolean;stop_reason:string|null;
}
export const activeScoutingRun=(r:ScoutingRun|null|undefined)=>!!r&&['queued','running','stopping'].includes(r.status);
export function scoutingUsage(r:ScoutingRun){
 const provider=r.attempts.filter(a=>a.kind==='provider');
 return {providerAttempts:provider.length,modelAttempts:r.attempts.filter(a=>a.kind==='model').length,confirmedCredits:provider.reduce((sum,a)=>sum+(a.actual_microcredits??0),0)/1e6,reservedCredits:provider.filter(a=>a.actual_microcredits===null).reduce((sum,a)=>sum+a.quoted_microcredits,0)/1e6,unknownReceipts:provider.filter(a=>a.actual_microcredits===null).length,newCases:new Set(r.candidates.flatMap(c=>c.case_id?[c.case_id]:[])).size,completeCases:new Set(r.completed_case_ids).size};
}
export function readScoutingRun(input:unknown):ScoutingRun{
 if(!input||typeof input!=='object')throw Error('Scouting run is not reported.');
 const r=input as ScoutingRun;
 if(typeof r.id!=='string'||!['queued','running','stopping','stopped','completed','failed','interrupted'].includes(r.status)||!Number.isFinite(Date.parse(r.deadline))||!r.limits||!Array.isArray(r.attempts)||!Array.isArray(r.candidates)||!Array.isArray(r.completed_case_ids)||r.attempts.some(a=>!['provider','model'].includes(a.kind)||typeof a.quoted_microcredits!=='number'||(a.actual_microcredits!==null&&typeof a.actual_microcredits!=='number')))throw Error('Unsupported scouting run status.');
 return r;
}
