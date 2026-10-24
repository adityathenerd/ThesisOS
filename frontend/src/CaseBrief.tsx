import {ArrowRight,ChevronRight,FileSearch,Share2} from 'lucide-react';
import type {CaseDetail} from './types';
import type {BriefClaim} from './case-brief';
import {resolveBrief} from './case-brief';
import ResearchWork from './ResearchWork';
import {currentWork} from './research-work';
import type {ResearchWorkView} from './research-work';

function Citations({ids,detail,onEvidence}:{ids:string[];detail:CaseDetail;onEvidence:(id:string)=>void}){
 return <span className="brief-citations">{[...new Set(ids)].map(id=>{const index=detail.evidence.findIndex(item=>item.id===id);return <button key={id} onClick={()=>onEvidence(id)} aria-label={`Inspect evidence ${index+1}: ${detail.evidence[index]?.claim_type.replaceAll('_',' ')??'unresolved source'}`}>[{index+1}]</button>;})}</span>;
}
export default function CaseBrief({detail,work=null,onEvidence,onView}:{detail:CaseDetail;work?:ResearchWorkView|null;onEvidence:(id:string)=>void;onView:(view:string)=>void}){
 const state=resolveBrief(detail);
 const reported=currentWork(work,detail.id,detail.version)&&(!state||state.status!=='available'||work.assessment_id===state.brief.assessment_id);
 if(state.status!=='available')return <section className="brief-pending" aria-label="Case brief"><span className="eyebrow">{state.status==='missing'?'BRIEF PENDING':'BRIEF NEEDS REFRESH'}</span><h3>What does this company do—and why investigate?</h3><p>{state.message}</p><p>Product, customer and attributable founder work remain unsummarized here. Existing research is still available.</p><ResearchWork work={work} caseId={detail.id} caseVersion={detail.version}/><div className="row wrap"><button className="secondary" onClick={()=>onView('evidence')}><FileSearch size={15}/>Inspect saved sources</button><button className="text-button" onClick={()=>onView('history')}>Saved assessments <ArrowRight size={14}/></button></div></section>;
 const {brief}=state;
 const claim=(item:BriefClaim)=><>{item.text}<Citations ids={item.evidence_ids} detail={detail} onEvidence={onEvidence}/></>;
 return <section className="case-brief-primary" aria-label="Case brief"><div className="brief-business"><div className="row between wrap"><span className="eyebrow">WHAT THE COMPANY DOES</span>{brief.origin==='editorial_saved_evidence'&&<span className="brief-editorial">Editorial summary</span>}</div><p>{claim(brief.business)}</p></div>
 <ResearchWork work={reported?work:null} caseId={detail.id} caseVersion={detail.version}/>
 <div className={`brief-answer ${brief.decision} ${reported?'secondary-recommendation':''}`}><span className="brief-decision">{reported?(brief.decision==='pursue'?'Agent recommendation: further research':'Agent recommendation: monitor'):brief.decision==='pursue'?'Pursue':'Monitor'}</span><h3>{claim(brief.recommendation)}</h3></div>
 <div className="brief-reasons" aria-label="Two strongest reasons">{brief.reasons.map((reason,index)=><article key={index}><span>0{index+1}</span><p>{claim(reason)}</p></article>)}</div>
 <section className="brief-founders" aria-label="Founder and team evidence"><span className="eyebrow">FOUNDER & TEAM EVIDENCE</span>{brief.founder_signals.length?brief.founder_signals.map((signal,index)=><article key={index}><div className="row between wrap"><h4>{signal.person}</h4><span className="brief-source-strength">{signal.source_strength}</span></div><p><strong>{signal.contribution}</strong> {signal.relevance}<Citations ids={signal.evidence_ids} detail={detail} onEvidence={onEvidence}/></p><small>{signal.limitation}</small></article>):<p>No attributable founder or team contribution has been established in the saved research.</p>}{brief.founder_unknown&&<p className="brief-founder-unknown">Still unknown: {brief.founder_unknown}</p>}</section>
 <div className="brief-bottom"><article className="brief-doubt"><span className="eyebrow">DECISIVE DOUBT</span><p>{claim(brief.decisive_doubt)}</p></article><article className="brief-action"><span className="eyebrow">{brief.decision==='monitor'?'REOPEN WHEN':'NEXT ACTION'}</span><p>{claim(brief.next_action)}</p></article></div>
 {brief.material_caveats.length>0&&<div className="brief-caveats">{brief.material_caveats.join(' ')}</div>}
 <div className="brief-navigation"><button className="secondary" onClick={()=>onView('evidence')}><FileSearch size={15}/>Sources & full analysis<ChevronRight size={13}/></button><button className="text-button" onClick={()=>onView('graph')}><Share2 size={15}/>Research graph</button><span>Research recommendation · human qualification separate</span></div>
 <details className="brief-provenance"><summary>Summary provenance & saved state</summary><p>{brief.origin==='editorial_saved_evidence'?'Editorial summary of saved evidence and the existing research recommendation. No new model call.':'Concise view of the saved agent assessment; not new factual evidence.'}</p><p>Case v{brief.case_version} · assessment {brief.assessment_id}. Operational disposition: {detail.status.replaceAll('_',' ')}. A pursue/monitor recommendation does not approve qualification or outreach.</p>{brief.operational_limitations?.length?<p>Execution limits: {brief.operational_limitations.join(' ')}</p>:null}</details>
 </section>;
}
