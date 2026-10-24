import type {Evidence,Evaluation,CaseDetail} from './types';

export function savedSemanticResults(details:CaseDetail[]){
 return {evaluations:details.reduce((n,c)=>n+c.evaluations.filter(e=>e.evaluator_kind==='semantic').length,0),comparisons:details.reduce((n,c)=>n+(c.agent_assessments??[]).filter(a=>a.driver_kind==='semantic'&&!!a.structured_result?.assessment&&a.comparison_only).length,0)};
}

export function evaluatorStatus(evaluation:Evaluation|null|undefined){
 if(evaluation?.evaluator_kind==='fixture')return {kind:'fixture' as const,label:'Fixture harness · no semantic result'};
 if(evaluation?.evaluator_kind==='semantic')return {kind:'semantic' as const,label:'Semantic assessment saved'};
 return {kind:'unknown' as const,label:'Evaluator unknown'};
}

export function evidenceBasis(evaluation:Evaluation,evidence:Evidence[]){
 const counts={live:0,captured:0,synthetic:0,unknown:0};
 const byId=new Map(evidence.map(item=>[item.id,item]));
 for(const id of new Set(evaluation.evidence_ids)){
  const item=byId.get(id);
  if(item&&(item.data_mode==='live'||item.data_mode==='captured'||item.data_mode==='synthetic'))counts[item.data_mode]++;
  else counts.unknown++;
 }
 return counts;
}
