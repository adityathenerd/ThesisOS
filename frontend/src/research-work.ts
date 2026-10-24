import type {Case} from './types';

export type ResearchState='research_required'|'actively_researching'|'reassessment_required'|'ready_for_human_review'|'monitor'|'human_research_required'|'supported_outside_scope'|'decline';
export interface ResearchQuestionView{id:string;question:string;attempts:string[];decision_consequence:string;next_source:string|null;why_stopped:string}
export interface ResearchWorkView{case_id:string;case_version:number;assessment_id:string|null;current:boolean;state:ResearchState;action:string;updated_at:string|null;attempts:{id:string;question_id:string;label:string;status:string;outcome:string;at:string|null;source_url:string|null}[];active_task_ids:string[];human_questions:ResearchQuestionView[];trigger:string|null;note:string|null;review_kind:string|null;review_packet:{label:string;evidence_ids:string[];interpretation_source:string|null}|null}
const labels:Record<ResearchState,string>={research_required:'Research proposed',actively_researching:'Actively researching',reassessment_required:'Reassessment needed',ready_for_human_review:'Ready for human review',monitor:'Monitoring a specific trigger',human_research_required:'Human research needed',supported_outside_scope:'Outside the mandate',decline:'Decline'};
export function currentWork(work:ResearchWorkView|null|undefined,caseId:string,caseVersion:number):work is ResearchWorkView{return !!work&&work.current&&work.case_id===caseId&&work.case_version===caseVersion}
export function workLabel(work:ResearchWorkView|null|undefined,caseId:string,caseVersion:number){
 if(!work)return 'Next-step execution not reported';
 if(!currentWork(work,caseId,caseVersion))return 'Work status needs refresh';
 return labels[work.state];
}
type RecordValue=Record<string,unknown>;
const record=(v:unknown):RecordValue=>v&&typeof v==='object'&&!Array.isArray(v)?v as RecordValue:{};
const strings=(v:unknown)=>Array.isArray(v)?v.filter((x):x is string=>typeof x==='string'):[];
const text=(v:unknown)=>typeof v==='string'?v:'';
const equalRef=(a:RecordValue,b:RecordValue)=>['case_id','case_version','thesis_version','policy_version','evidence_hash'].every(key=>a[key]!==undefined&&a[key]===b[key]);

// A read-only projection. Proposed intents never become active tasks, and
// historical attempts stay separate from the current unresolved questions.
export function readResearchWork(input:unknown,item:Case,assessmentId?:string):ResearchWorkView{
 const data=record(input),workflow=record(data.workflow),ref=record(workflow.input_ref),assessmentRef=record(workflow.assessment_input_ref);
 if(data.case_id!==item.id||typeof data.case_version!=='number'||!(text(workflow.state) in labels)||typeof workflow.explanation!=='string')throw new Error('Unrecognized research work record');
 const attempts=(Array.isArray(data.attempts)?data.attempts:[]).map(record).map(a=>({id:text(a.task_id),question_id:text(a.question_id),label:text(a.summary),status:text(a.status),outcome:text(a.status).replaceAll('_',' '),at:text(a.attempted_at)||null,source_url:strings(a.source_urls).find(url=>/^https?:\/\//i.test(url))??null}));
 const reassessment=workflow.state==='reassessment_required';
 const current=data.case_version===item.version&&ref.case_id===item.id&&ref.case_version===item.version&&workflow.assessment_ref===data.assessment_id&&(!assessmentId||assessmentId===data.assessment_id)&&(reassessment||(data.assessment_current===true&&equalRef(ref,assessmentRef)));
 const questions=(Array.isArray(workflow.human_research_points)?workflow.human_research_points:[]).map(record).map(q=>({id:text(q.question_id),question:text(q.question),decision_consequence:text(q.decision_consequence),next_source:text(q.what_to_obtain)||null,why_stopped:text(q.why_agent_stopped),attempts:attempts.filter(a=>strings(q.attempted_task_ids).includes(a.id)).map(a=>`${a.label} (${a.outcome})`)}));
 const packet=record(data.available_review_packet);
 const review_packet=current&&packet.kind==='specialist_evidence_review'&&packet.formal_partner_review_ready===false&&packet.qualification_accepted===false&&text(packet.label)&&strings(packet.evidence_ids).length?{label:text(packet.label),evidence_ids:strings(packet.evidence_ids),interpretation_source:text(packet.interpretation_source)||null}:null;
 return {case_id:item.id,case_version:data.case_version,assessment_id:text(data.assessment_id)||null,current,state:workflow.state as ResearchState,action:workflow.explanation,updated_at:attempts.flatMap(a=>a.at?[a.at]:[]).sort().at(-1)??null,attempts,active_task_ids:strings(workflow.active_task_ids),human_questions:questions,trigger:text(workflow.future_trigger)||null,note:text(data.execution_note)||null,review_kind:text(workflow.review_kind)||null,review_packet};
}

export function observedResearchTasks(works:Record<string,ResearchWorkView>,cases:Case[]){
 return cases.flatMap(item=>{const work=works[item.id];if(!currentWork(work,item.id,item.version)||work.state!=='actively_researching')return [];return work.attempts.filter(a=>work.active_task_ids.includes(a.id)&&['running','queued'].includes(a.status)).map(attempt=>({company:item.company_name,case_id:item.id,...attempt}));});
}
