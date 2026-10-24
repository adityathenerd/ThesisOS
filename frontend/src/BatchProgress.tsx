import {RefreshCw} from 'lucide-react';
import type {ResearchBatch} from './types';

export default function BatchProgress({batch,error,onRefresh}:{batch:ResearchBatch|null;error:string;onRefresh:()=>void}){
 if(!batch)return null;
 const p=batch.progress;
 return <section className="batch-progress" aria-label="Research batch progress"><div className="batch-progress-main"><div><span className="eyebrow">RESEARCH BATCH</span><h2>{p.completed_cases}<small> / {batch.target_new_researched_cases}</small> scouts researched</h2><p>{batch.status.replaceAll('_',' ')} · {p.unique_pool} unique companies in pool · {p.selected_cases} selected</p></div><button className="secondary" onClick={onRefresh}><RefreshCw size={14}/>Refresh results</button></div><progress max={batch.target_new_researched_cases} value={Math.min(p.completed_cases,batch.target_new_researched_cases)} aria-label="Completed researched scouts"/><div className="batch-progress-note"><span>Research completion is separate from qualification and outreach.</span><span>Saved {new Date(batch.updated_at).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})}</span></div>{batch.shortfall_reason&&<p className="batch-shortfall">{batch.shortfall_reason}</p>}{error&&<p className="batch-shortfall" role="status">Progress could not be refreshed. These are the last saved counts. {error}</p>}</section>;
}
