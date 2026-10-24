import type {Evidence,Evaluation,Mandate} from './types';
import {evaluatorStatus,evidenceBasis} from './provenance';

export default function AssessmentBasis({evaluation,evidence,referenceStatus}:{evaluation:Evaluation;evidence:Evidence[];referenceStatus:Mandate['reference_status']|undefined}){
 const status=evaluatorStatus(evaluation),counts=evidenceBasis(evaluation,evidence);
 const sources=Object.entries(counts).filter(([,count])=>count>0).map(([mode,count])=>`${count} ${mode}`).join(' · ');
 return <div className={`assessment-basis ${status.kind}`} aria-label="Assessment basis"><div><span>Saved result</span><strong>{status.label}</strong></div><div><span>Referenced evidence</span><strong>{sources||'No evidence referenced'}</strong></div><div><span>Thesis input · v{evaluation.thesis_version}</span><strong>{referenceStatus==='placeholder'?'Placeholder · illustrative only':referenceStatus==='user_supplied'?'User-supplied text':'Reference status unknown'}</strong></div><div><span>Policy approval</span><strong>Approval status not reported</strong></div>{status.kind==='semantic'&&<p>Model reasoning is saved separately from the underlying evidence. Live, captured, synthetic and replayed inputs retain their own labels.</p>}</div>;
}
