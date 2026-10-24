import {useEffect,useState} from 'react';
import {Loader2,RefreshCw} from 'lucide-react';
import ResearchGraph from './ResearchGraph';
import {validateGraph} from './research-graph';
import type {Transport} from './types';

export default function CaseResearchGraph({api,caseId,caseVersion,assessmentId}:{api:Transport;caseId:string;caseVersion:number;assessmentId:string|null}){
 const [state,setState]=useState<{loading:boolean;artifact:unknown;error:string}>({loading:true,artifact:null,error:''}),[generation,setGeneration]=useState(0);
 useEffect(()=>{let active=true;setState({loading:true,artifact:null,error:''});(async()=>{try{if(!api.researchGraph)throw new Error('Research graphs are not provided by this transport.');const graph=validateGraph(await api.researchGraph(caseId));if(graph.case_id!==caseId||graph.research_example_ref)throw new Error('The returned graph does not belong to this saved case.');if(graph.snapshot_ref.case_version!==caseVersion)throw new Error('The graph snapshot and current case version differ. Refresh saved case state before continuing.');if(active)setState({loading:false,artifact:graph,error:''});}catch(e){if(active)setState({loading:false,artifact:null,error:(e as Error).message});}})();return()=>{active=false};},[api,caseId,caseVersion,assessmentId,generation]);
 if(state.loading)return <div className="loading-panel" role="status"><Loader2 className="spin"/>Loading the saved case graph…</div>;
 if(state.error)return <section className="case-graph-empty" role="status"><h3>Case graph unavailable</h3><p>{state.error}</p><p>The connected backend must serve this case’s versioned graph. Captured examples remain separate in Thesis & tracks.</p><button className="secondary" onClick={()=>setGeneration(n=>n+1)}><RefreshCw size={14}/>Refresh graph</button></section>;
 return <ResearchGraph key={`${caseId}:${caseVersion}:${assessmentId}:${generation}`} artifact={state.artifact}/>;
}
