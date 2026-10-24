import type {CaseDetail} from './types';
import type {ResearchWorkView} from './research-work';

export function mergeAssessmentRevisions(previous:Record<string,string>,works:Record<string,ResearchWorkView>){
 let next=previous;
 for(const work of Object.values(works)){
  if(!work.current||!work.assessment_id||previous[work.case_id]===work.assessment_id)continue;
  if(next===previous)next={...previous};
  next[work.case_id]=work.assessment_id;
 }
 return next;
}
export function latestAssessmentId(detail:CaseDetail|null){
 return detail?.agent_assessments?.reduce((latest,item)=>!latest||item.created_at>latest.created_at?item:latest,null as NonNullable<CaseDetail['agent_assessments']>[number]|null)?.id??null;
}
