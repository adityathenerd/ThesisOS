import {Clock3,HelpCircle,Loader2,RefreshCw,UserRoundCheck} from 'lucide-react';
import {currentWork,workLabel} from './research-work';
import type {ResearchWorkView} from './research-work';

export default function ResearchWork({work,caseId,caseVersion,onRefresh,compact=false}:{work:ResearchWorkView|null;caseId:string;caseVersion:number;onRefresh?:()=>void;compact?:boolean}){
 const current=currentWork(work,caseId,caseVersion),label=workLabel(work,caseId,caseVersion);
 return <section className={`research-work ${current?work.state:'unreported'} ${compact?'compact':''}`} aria-label="Research follow-up and readiness">
  <div className="research-work-heading"><div className="row"><span className="work-state-symbol">{current&&work.state==='actively_researching'?<Loader2 className="spin" size={15}/>:current&&work.state==='ready_for_human_review'?<UserRoundCheck size={15}/>:current&&work.state==='human_research_required'?<HelpCircle size={15}/>:<Clock3 size={15}/>}</span><strong>{label}</strong></div>{onRefresh&&<button className="text-button" onClick={onRefresh}><RefreshCw size={12}/>Refresh work</button>}</div>
  {!current?<p>A pursue recommendation names a next research step. Its execution and subsequent reassessment are not reported for this snapshot.</p>:<>
   <p>{work.action}</p>
   {work.review_packet&&<aside className="specialist-review-packet" title={work.review_packet.interpretation_source??undefined}><strong>{work.review_packet.label}</strong><small>Thesis interpretation · human research handoff. Formal partner review and qualification remain unapproved.</small></aside>}
   {work.trigger&&<p className="work-trigger"><strong>Reopen when:</strong> {work.trigger}</p>}
   {work.state==='human_research_required'&&<div className="human-research-questions">{work.human_questions.length?work.human_questions.map(question=><article key={question.id}>
    <h4>{question.question}</h4>
    {question.next_source&&<p><strong>Evidence to obtain:</strong> {question.next_source}</p>}
    <details className="question-research-detail"><summary>Why this matters / what was tried <span>{question.attempts.length} linked {question.attempts.length===1?'attempt':'attempts'}</span></summary>
     <p><strong>Why it changes the case:</strong> {question.decision_consequence}</p>
     {question.why_stopped&&<p><strong>Why the agent stopped:</strong> {question.why_stopped}</p>}
     {question.attempts.length>0&&<><p><strong>Already attempted:</strong></p><ul>{question.attempts.map((attempt,index)=><li key={index}>{attempt}</li>)}</ul></>}
    </details>
   </article>):<p>Human research is required, but the backend has not supplied the exact questions. Refresh the saved work record.</p>}</div>}
   {work.attempts.length>0&&<details className="research-attempts"><summary>{work.attempts.length} saved research attempts</summary>{work.attempts.map(attempt=><article key={attempt.id}><strong>{attempt.label}</strong><span>{attempt.outcome}</span>{attempt.at&&<time>{new Date(attempt.at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})}</time>}{attempt.source_url&&/^https?:\/\//i.test(attempt.source_url)&&<a href={attempt.source_url} target="_blank" rel="noreferrer">Source ↗</a>}</article>)}</details>}
   {work.note&&<p className="research-work-note">{work.note}</p>}
   {work.review_kind&&<p>Next owner: {work.review_kind==='specialist_human'?'Specialist reviewer':'Investment reviewer'}</p>}
   {work.updated_at&&<small>Last attempt {new Date(work.updated_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})}</small>}
  </>}
 </section>;
}
