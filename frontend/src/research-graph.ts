export interface TemporalScope{precision:'unknown'|'year'|'month'|'day'|'datetime'|'interval';value:string|null;start:string|null;end:string|null;basis:'unknown'|'publication'|'observation'|'retrieval'|'event'|'reported_as_of';limitation:string|null}
export interface VersionRef{case_id:string;case_version:number;thesis_version:number;policy_version:number;evidence_hash:string}
export type GraphNodeKind='person'|'organisation'|'product'|'asset'|'project'|'event'|'post'|'topic'|'award'|'claim'|'source';
export interface GraphSource{id:string;evidence_ids:string[];source_url:string|null;source_keys:string[];source_type:string;source_quality:string;data_mode:'live'|'captured'|'synthetic';publication_time:TemporalScope;observation_times:TemporalScope[];retrieval_times:TemporalScope[];limitations:string[]}
export interface GraphNode{id:string;kind:GraphNodeKind;label:string;canonical_entity_ref:{kind:string;id:string}|null;source_refs:string[];attributes:Record<string,string|number|boolean|null>;temporal_scope:TemporalScope}
export interface GraphEdge{id:string;from_id:string;to_id:string;relation:string;label:string;evidence_ids:string[];source_refs:string[];assertion_kind:'source_reported'|'observed'|'inferred';support_status:'supported'|'mixed'|'contradicted'|'unknown';temporal_scope:TemporalScope;limitation:string;interpretation_ref:string|null;event_ref?:string|null}
export interface GraphQuestion{id:string;target_node_ids:string[];target_edge_ids:string[];criterion_ids:string[];question:string;decision_consequence:string}
export interface MatcherInterpretation{id:string;assessment_ref:string;input_ref:VersionRef;prompt_version:string;driver_kind:'scripted'|'semantic';criterion_id:string;target_node_ids:string[];evidence_ids:string[];counterevidence_ids:string[];source_refs:string[];comparison_state:'supported'|'mixed'|'contradicted'|'unknown'|'not_applicable';interpretation:string;authority:'model_interpretation_not_new_evidence'}
export interface ResearchAnswer{summary:string;evidence_ids:string[];source_refs:string[];objections:string[];unknowns:string[]}
export interface MatcherSummary{assessment_ref:string;input_ref:VersionRef;prompt_version:string;driver_kind:'scripted'|'semantic';why_this:ResearchAnswer;why_them:ResearchAnswer;why_now:ResearchAnswer;team_problem_fit:ResearchAnswer;authority:'model_interpretation_not_new_evidence'}
export interface ResearchDecision{assessment_ref:string;input_ref:VersionRef;decision:'pursue'|'monitor';next_action:string;decision_consequence:string;future_trigger:string|null;evidence_ids:string[];source_refs:string[];assertion_kind:'inferred';qualification_note:string}
export interface EcosystemInterpretation{id:string;input_ref:VersionRef;person_id:string;topic_id:string;supporting_edge_ids:string[];evidence_ids:string[];source_refs:string[];temporal_scope:TemporalScope;explanation:string;authority:'derived_observed_topic_engagement_not_personality_or_friendship'}
export interface RepeatedDatedTie{from_id:string;to_id:string;relation:string;event_refs:string[];dates:string[];evidence_ids:string[]}
export interface EcosystemCoverage{unique_entities:number;entities_by_kind:Record<string,number>;supported_typed_edges:number;typed_relationship_types:string[];dated_event_ids:string[];repeated_dated_ties:RepeatedDatedTie[];full_network_density:null;limitations:string[]}
export interface ResearchGraph{schema_version:'0.1';graph_id:string;case_id:string|null;research_example_ref:string|null;snapshot_ref:VersionRef;generated_at:string;nodes:GraphNode[];edges:GraphEdge[];sources:GraphSource[];open_questions:GraphQuestion[];matcher_interpretations:MatcherInterpretation[];matcher_summary?:MatcherSummary|null;research_decision?:ResearchDecision|null;ecosystem_interpretations?:EcosystemInterpretation[];ecosystem_coverage?:EcosystemCoverage|null;limitations:string[]}

const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const strings=(v:unknown):v is string[]=>Array.isArray(v)&&v.every(x=>typeof x==='string');
function temporal(v:unknown){if(!object(v)||!['unknown','year','month','day','datetime','interval'].includes(String(v.precision))||!['unknown','publication','observation','retrieval','event','reported_as_of'].includes(String(v.basis)))throw new Error('Invalid temporal precision or basis.');for(const key of ['value','start','end','limitation'])if(v[key]!==null&&v[key]!==undefined&&typeof v[key]!=='string')throw new Error('Invalid temporal value.');}
export function validateGraph(input:unknown):ResearchGraph{
 if(!object(input)||input.schema_version!=='0.1')throw new Error('Unsupported research graph schema.');
 for(const key of ['graph_id','generated_at'])if(typeof input[key]!=='string'||!input[key])throw new Error(`Research graph is missing ${key}.`);
 if((!!input.case_id)===(!!input.research_example_ref))throw new Error('A graph must identify one saved case or one explicit research example.');
 if(!object(input.snapshot_ref)||typeof input.snapshot_ref.case_id!=='string'||!Number.isInteger(input.snapshot_ref.case_version)||!Number.isInteger(input.snapshot_ref.thesis_version)||!Number.isInteger(input.snapshot_ref.policy_version)||typeof input.snapshot_ref.evidence_hash!=='string')throw new Error('Research graph has no valid snapshot binding.');
 if(input.case_id&&input.snapshot_ref.case_id!==input.case_id)throw new Error('Graph snapshot belongs to a different case.');
 for(const key of ['nodes','edges','sources','open_questions','matcher_interpretations','limitations'])if(!Array.isArray(input[key]))throw new Error(`Research graph is missing ${key}.`);
 const graph=input as unknown as ResearchGraph;
 const unique=(items:{id:string}[],kind:string)=>{const ids=new Set<string>();for(const item of items){if(!object(item)||typeof item.id!=='string'||!item.id||ids.has(item.id))throw new Error(`Graph ${kind} must have unique IDs.`);ids.add(item.id);}return ids;};
 const nodeIds=unique(graph.nodes,'nodes'),edgeIds=unique(graph.edges,'edges'),sourceIds=unique(graph.sources,'sources'),interpretationIds=unique([...graph.matcher_interpretations,...graph.ecosystem_interpretations??[]],'interpretations');unique(graph.open_questions,'questions');
 const refs=(values:unknown,ids:Set<string>,kind:string)=>{if(!strings(values)||values.some(id=>!ids.has(id)))throw new Error(`Dangling or invalid ${kind} reference.`);};
 const evidenceIds=new Set<string>();
 const binding=(ref:VersionRef)=>{if(!object(ref)||(['case_id','case_version','thesis_version','policy_version','evidence_hash'] as const).some(key=>ref[key]!==graph.snapshot_ref[key]))throw new Error('Interpretation snapshot differs from the graph snapshot.');};
 const cited=(item:{evidence_ids:string[];source_refs:string[]})=>{refs(item.source_refs,sourceIds,'source');refs(item.evidence_ids,evidenceIds,'evidence');const citedIds=new Set(graph.sources.filter(s=>item.source_refs.includes(s.id)).flatMap(s=>s.evidence_ids));if(item.evidence_ids.some(id=>!citedIds.has(id)))throw new Error('Evidence is not included in the cited source group.');};
 for(const source of graph.sources){if(!strings(source.evidence_ids)||!strings(source.source_keys)||!strings(source.limitations)||!['live','captured','synthetic'].includes(source.data_mode))throw new Error('Invalid graph source provenance.');source.evidence_ids.forEach(id=>evidenceIds.add(id));temporal(source.publication_time);if(!Array.isArray(source.observation_times)||!Array.isArray(source.retrieval_times))throw new Error('Invalid graph source times.');source.observation_times.forEach(temporal);source.retrieval_times.forEach(temporal);}
 for(const node of graph.nodes){if(!['person','organisation','product','asset','project','event','post','topic','award','claim','source'].includes(node.kind)||typeof node.label!=='string')throw new Error('Invalid graph node.');refs(node.source_refs,sourceIds,'source');temporal(node.temporal_scope);}
 for(const edge of graph.edges){if(!nodeIds.has(edge.from_id)||!nodeIds.has(edge.to_id))throw new Error('Graph contains an orphan relationship endpoint.');refs(edge.source_refs,sourceIds,'source');refs(edge.evidence_ids,evidenceIds,'evidence');if(!['source_reported','observed','inferred'].includes(edge.assertion_kind)||!['supported','mixed','contradicted','unknown'].includes(edge.support_status))throw new Error('Unknown graph relationship assertion or support.');if(edge.interpretation_ref&&!interpretationIds.has(edge.interpretation_ref))throw new Error('Dangling matcher interpretation reference.');temporal(edge.temporal_scope);}
 for(const question of graph.open_questions){refs(question.target_node_ids,nodeIds,'question node');refs(question.target_edge_ids,edgeIds,'question edge');}
 for(const interpretation of graph.matcher_interpretations){refs(interpretation.target_node_ids,nodeIds,'interpretation node');cited(interpretation);refs(interpretation.counterevidence_ids,evidenceIds,'counterevidence');binding(interpretation.input_ref);if(interpretation.authority!=='model_interpretation_not_new_evidence')throw new Error('Unknown interpretation authority.');}
 for(const interpretation of graph.ecosystem_interpretations??[]){binding(interpretation.input_ref);cited(interpretation);refs(interpretation.supporting_edge_ids,edgeIds,'topic supporting edge');if(graph.nodes.find(n=>n.id===interpretation.person_id)?.kind!=='person'||graph.nodes.find(n=>n.id===interpretation.topic_id)?.kind!=='topic'||interpretation.authority!=='derived_observed_topic_engagement_not_personality_or_friendship')throw new Error('Invalid ecosystem interpretation identity or authority.');temporal(interpretation.temporal_scope);}
 for(const edge of graph.edges)if(edge.event_ref&&(!nodeIds.has(edge.event_ref)||!['event','post','project','asset'].includes(graph.nodes.find(n=>n.id===edge.event_ref)!.kind)))throw new Error('Invalid relationship event reference.');
 if(graph.ecosystem_coverage){const coverage=graph.ecosystem_coverage;if(coverage.full_network_density!==null)throw new Error('Observed ecosystem cannot assert full network density.');refs(coverage.dated_event_ids,nodeIds,'coverage event');for(const tie of coverage.repeated_dated_ties){if(!nodeIds.has(tie.from_id)||!nodeIds.has(tie.to_id)||!['coauthored_with','collaborated_with'].includes(tie.relation)||new Set(tie.event_refs).size<2||new Set(tie.dates).size<2)throw new Error('Repeated work requires distinct sourced events and dates.');refs(tie.event_refs,nodeIds,'repeated work event');refs(tie.evidence_ids,evidenceIds,'repeated work evidence');}}
 if(graph.matcher_summary){binding(graph.matcher_summary.input_ref);if(graph.matcher_summary.authority!=='model_interpretation_not_new_evidence')throw new Error('Unknown summary authority.');for(const key of ['why_this','why_them','why_now','team_problem_fit'] as const)cited(graph.matcher_summary[key]);}
 if(graph.research_decision){const decision=graph.research_decision;binding(decision.input_ref);cited(decision);if(!['pursue','monitor'].includes(decision.decision)||decision.assertion_kind!=='inferred'||!decision.next_action||(decision.decision==='monitor'&&!decision.future_trigger))throw new Error('Invalid research decision or missing monitor trigger.');}
 return graph;
}
export function temporalText(time:TemporalScope|undefined){
 if(!time||time.precision==='unknown')return 'Unknown';
 const value=time.precision==='interval'?`${time.start??'Unknown start'} → ${time.end??'Unknown end'}`:time.value??'Unknown';
 return `${value} · ${time.precision} · ${time.basis.replaceAll('_',' ')}`;
}
function latestPossible(time:TemporalScope){
 if(time.precision==='unknown')return null;
 if(time.precision==='interval')return time.end??null;
 if(!time.value)return null;
 if(time.precision==='year')return `${time.value}-12-31`;
 if(time.precision==='month')return `${time.value}-31`;
 return time.value;
}
export function graphNeighborhood(graph:ResearchGraph,relation='all',since='',includeUndated=true,includeEvidence=true,focusId='all',depth=2){
 const displayed=graph.nodes.filter(node=>includeEvidence||!['claim','source'].includes(node.kind)),displayedIds=new Set(displayed.map(node=>node.id));
 const filtered=graph.edges.filter(edge=>{if(!displayedIds.has(edge.from_id)||!displayedIds.has(edge.to_id))return false;if(relation!=='all'&&edge.relation!==relation)return false;const date=latestPossible(edge.temporal_scope);return date?(!since||date.slice(0,10)>=since):includeUndated;});
 const connected=new Set(filtered.flatMap(edge=>[edge.from_id,edge.to_id]));
 let candidates=relation==='all'&&!since&&includeUndated?displayed:displayed.filter(node=>connected.has(node.id)||node.kind==='organisation');
 if(focusId!=='all'){const distance=new Map<string,number>([[focusId,0]]);for(let step=0;step<depth;step++){const before=new Set([...distance].filter(([,d])=>d<=step).map(([id])=>id));for(const edge of filtered){if(before.has(edge.from_id)&&!distance.has(edge.to_id))distance.set(edge.to_id,step+1);if(before.has(edge.to_id)&&!distance.has(edge.from_id))distance.set(edge.from_id,step+1);}}candidates=displayed.filter(node=>distance.has(node.id)).sort((a,b)=>distance.get(a.id)!-distance.get(b.id)!);}
 const nodes=candidates.slice(0,24),ids=new Set(nodes.map(node=>node.id));
 const edges=filtered.filter(edge=>ids.has(edge.from_id)&&ids.has(edge.to_id)).slice(0,48);
 return{nodes,edges,limited:nodes.length<candidates.length||edges.length<filtered.length};
}
export function graphLayout(nodes:GraphNode[],centerId='all'){
 const positions=new Map<string,{x:number;y:number}>(),center=nodes.find(node=>node.id===centerId)??nodes.find(node=>node.kind==='organisation');
 if(center)positions.set(center.id,{x:480,y:300});
 const order=['person','organisation','project','product','asset','post','topic','event','award','claim','source'];
 const others=nodes.filter(node=>node.id!==center?.id).sort((a,b)=>order.indexOf(a.kind)-order.indexOf(b.kind));
 others.forEach((node,index)=>{const angle=-Math.PI/2+index*2*Math.PI/Math.max(others.length,1);positions.set(node.id,{x:480+345*Math.cos(angle),y:300+225*Math.sin(angle)})});
 return positions;
}
