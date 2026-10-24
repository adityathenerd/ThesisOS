import {MessageCircle,UserRound,Link2} from 'lucide-react';
import type {CaseDetail} from './types';

// Presentation only. The wire adapter supplies every decision and source link.
export interface ConversationReviewView{
 label:string;tone:'candidate'|'research'|'monitor'|'outside';
 rationale:{text:string;evidence_ids:string[]};counterpoint:{text:string;evidence_ids:string[]}|null;
 person:{label:string;detail:string};contact:{label:string;detail:string};
 questions:{id:string;question:string;context:string|null;evidence_ids:string[]}[];
}
export default function ConversationReview({review,detail,onEvidence}:{review:ConversationReviewView;detail:CaseDetail;onEvidence:(id:string)=>void}){
 const references=(ids:string[])=><span className="brief-citations">{ids.map(id=>{const index=detail.evidence.findIndex(e=>e.id===id);return index<0?null:<button key={id} onClick={()=>onEvidence(id)} aria-label={`Inspect evidence ${index+1}: pre-outreach review source`}>[{index+1}]</button>;})}</span>;
 return <section className={`conversation-review ${review.tone}`} aria-label="Pre-outreach conversation review">
  <div className="conversation-review-heading"><span className="eyebrow"><MessageCircle size={14}/>WORTH AN INTRODUCTORY CONVERSATION?</span><strong>{review.label}</strong></div>
  <p className="conversation-rationale">{review.rationale.text}{references(review.rationale.evidence_ids)}</p>
  {review.counterpoint&&<p className="conversation-counterpoint"><strong>Keep in view:</strong> {review.counterpoint.text}{references(review.counterpoint.evidence_ids)}</p>}
  <div className="conversation-preparation"><div><span><UserRound size={13}/>RELEVANT PERSON</span><strong>{review.person.label}</strong><p>{review.person.detail}</p></div><div><span><Link2 size={13}/>CONTACT PREPARATION</span><strong>{review.contact.label}</strong><p>{review.contact.detail}</p></div></div>
  {review.questions.length>0&&<div className="conversation-questions"><span className="eyebrow">DISCOVERY QUESTIONS</span>{review.questions.map((question,index)=><article key={question.id}><span>0{index+1}</span><div><h4>{question.question}{references(question.evidence_ids)}</h4>{question.context&&<p>{question.context}</p>}</div></article>)}</div>}
  <p className="conversation-authority">Human-authorized pre-outreach interpretation of saved evidence. Formal readiness, qualification and sending approval are separate.</p>
 </section>;
}
