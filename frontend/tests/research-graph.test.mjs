import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {validateGraph,graphNeighborhood,graphLayout,temporalText} from '../src/research-graph.ts';

const read=()=>JSON.parse(fs.readFileSync(new URL('../src/reference/allodirect-research-graph.json',import.meta.url)));
test('the actual captured producer graph preserves source grouping, scope, interpretation, and portable JSON',()=>{
 const input=read(),graph=validateGraph(input);
 assert.equal(graph.case_id,null);assert.ok(graph.research_example_ref);
 assert.equal(graph.nodes.length,11);assert.equal(graph.edges.length,14);
 assert.equal(graph.sources.length,1);assert.equal(graph.sources[0].evidence_ids.length,5);
 assert.equal(graph.sources[0].data_mode,'captured');assert.equal(graph.matcher_interpretations.length,8);
 assert.equal(graph.research_decision.decision,'monitor');assert.ok(graph.research_decision.future_trigger);
 assert.deepEqual(JSON.parse(JSON.stringify(graph)),input);
 const entities=graphNeighborhood(graph,'all','',true,false);
 assert.ok(entities.nodes.length<graph.nodes.length);
 assert.ok(entities.nodes.every(n=>!['claim','source'].includes(n.kind)));
 assert.ok(entities.edges.some(e=>e.relation==='held_role_at'));
 assert.ok(graph.nodes.filter(n=>n.kind==='person').every(n=>n.temporal_scope.precision==='unknown'));
});
test('dangling nodes, sources, evidence, cross-snapshot interpretation and triggerless monitors are refused',()=>{
 for(const mutate of [g=>g.edges[0].to_id='missing',g=>g.edges[0].source_refs=['missing'],g=>g.edges[0].evidence_ids=['missing'],g=>g.matcher_summary.input_ref.case_version++,g=>g.research_decision.future_trigger=null]){
  const graph=read();mutate(graph);assert.throws(()=>validateGraph(graph));
 }
});
test('date/relation filtering retains unknown precision explicitly and never treats retrieval as role tenure',()=>{
 const graph=validateGraph(read());
 const all=graphNeighborhood(graph);
 const dated=graphNeighborhood(graph,'all','2026-10-01',false);
 assert.ok(dated.edges.length<all.edges.length);
 assert.ok(dated.edges.every(e=>e.temporal_scope.precision!=='unknown'));
 assert.equal(graphNeighborhood(graph,'missing').edges.length,0);
 assert.equal(temporalText({precision:'unknown'}),'Unknown');
 assert.match(temporalText({precision:'month',value:'2026-09',basis:'event'}),/^2026-09 · month · event$/);
 const positions=graphLayout(all.nodes);
 assert.equal(positions.size,all.nodes.length);
 for(const point of positions.values())assert.ok(Number.isFinite(point.x)&&Number.isFinite(point.y)&&point.x>0&&point.x<960&&point.y>0&&point.y<640);
});
test('empty graphs remain honest and large neighborhoods are bounded with no orphan edges',()=>{
 const graph=read();Object.assign(graph,{nodes:[],edges:[],sources:[],open_questions:[],matcher_interpretations:[],matcher_summary:null,research_decision:null});
 assert.equal(validateGraph(graph).nodes.length,0);
 assert.deepEqual(graphNeighborhood(graph),{nodes:[],edges:[],limited:false});
 const full=read();full.nodes=Array.from({length:35},(_,i)=>({...full.nodes[0],id:`n${i}`}));full.edges=Array.from({length:70},(_,i)=>({...full.edges[0],id:`e${i}`,from_id:`n${i%35}`,to_id:`n${(i+1)%35}`}));
 const view=graphNeighborhood(full),ids=new Set(view.nodes.map(n=>n.id));
 assert.ok(view.limited);assert.ok(view.nodes.length<=24);assert.ok(view.edges.length<=48);
 assert.ok(view.edges.every(e=>ids.has(e.from_id)&&ids.has(e.to_id)));
});

test('person-focused context uses only existing sourced edges and keeps the selected person centered',()=>{
 const graph=read(),person=graph.nodes.find(n=>n.kind==='person'),view=graphNeighborhood(graph,'all','',true,false,person.id,2);
 assert.ok(view.nodes.some(n=>n.id===person.id));assert.ok(view.nodes.every(n=>!['claim','source'].includes(n.kind)));
 const edgeIds=new Set(graph.edges.map(e=>e.id));assert.ok(view.edges.every(e=>edgeIds.has(e.id)));
 assert.deepEqual(graphLayout(view.nodes,person.id).get(person.id),{x:480,y:300});
 const empty=graphNeighborhood(graph,'missing','',true,false,person.id,2);assert.equal(empty.edges.length,0);assert.equal(empty.nodes.length,1);
});

test('ecosystem additions retain topic interpretations separately and refuse full-network or repeat-work inventions',()=>{
 const graph=read(),sourceId=graph.sources[0].id,evidenceId=graph.sources[0].evidence_ids[0],person=graph.nodes.find(n=>n.kind==='person');
 const temporal={precision:'day',value:'2026-09-25',start:null,end:null,basis:'event',limitation:'Synthetic UI boundary test'};
 for(const kind of ['post','topic','award'])graph.nodes.push({id:`synthetic-${kind}`,kind,label:`Synthetic ${kind}`,source_refs:[sourceId],attributes:{},canonical_entity_ref:null,temporal_scope:temporal});
 graph.edges.push({id:'synthetic-authored',from_id:person.id,to_id:'synthetic-post',relation:'authored',label:'Synthetic authorship boundary',evidence_ids:[evidenceId],source_refs:[sourceId],assertion_kind:'source_reported',support_status:'supported',temporal_scope:temporal,limitation:'Software test only',interpretation_ref:null,event_ref:'synthetic-post'});
 graph.ecosystem_interpretations=[{id:'synthetic-topic-interpretation',input_ref:structuredClone(graph.snapshot_ref),person_id:person.id,topic_id:'synthetic-topic',supporting_edge_ids:['synthetic-authored'],evidence_ids:[evidenceId],source_refs:[sourceId],temporal_scope:temporal,explanation:'Synthetic dated-content interpretation, not personality.',authority:'derived_observed_topic_engagement_not_personality_or_friendship'}];
 graph.edges.push({...graph.edges.at(-1),id:'synthetic-interest',to_id:'synthetic-topic',relation:'interest_in',assertion_kind:'inferred',interpretation_ref:'synthetic-topic-interpretation',event_ref:null});
 assert.equal(validateGraph(graph),graph);
 const stale=structuredClone(graph);stale.ecosystem_interpretations[0].input_ref.case_version++;assert.throws(()=>validateGraph(stale));
 const density=structuredClone(graph);density.ecosystem_coverage={full_network_density:.8,dated_event_ids:[],repeated_dated_ties:[]};assert.throws(()=>validateGraph(density));
 const repeat=structuredClone(graph);repeat.ecosystem_coverage={full_network_density:null,dated_event_ids:[],repeated_dated_ties:[{from_id:person.id,to_id:person.id,relation:'collaborated_with',event_refs:['synthetic-post'],dates:['2026-09-25'],evidence_ids:[evidenceId]}]};assert.throws(()=>validateGraph(repeat));
});
