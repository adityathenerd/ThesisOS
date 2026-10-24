import test from 'node:test';
import assert from 'node:assert/strict';
import {evaluatorStatus,evidenceBasis,savedSemanticResults} from '../src/provenance.ts';

test('configuration or a missing/unknown evaluator never becomes a semantic result',()=>{
 assert.equal(evaluatorStatus(null).kind,'unknown');
 assert.equal(evaluatorStatus({evaluator_kind:'configured'}).kind,'unknown');
 assert.equal(evaluatorStatus({evaluator_kind:'fixture'}).kind,'fixture');
 assert.equal(evaluatorStatus({evaluator_kind:'semantic'}).kind,'semantic');
});
test('basis counts only unique referenced observations, preserving mixed modes and unresolved references',()=>{
 const result=evidenceBasis({evidence_ids:['a','b','b','c','missing']},[
  {id:'a',data_mode:'live'},{id:'b',data_mode:'synthetic'},{id:'c',data_mode:'captured'},
  {id:'unused',data_mode:'live'},
 ]);
 assert.deepEqual(result,{live:1,captured:1,synthetic:1,unknown:1});
});
test('absence of references remains absence of evidence, rather than live or synthetic success',()=>{
 assert.deepEqual(evidenceBasis({evidence_ids:[]},[{id:'a',data_mode:'live'}]),{live:0,captured:0,synthetic:0,unknown:0});
});

test('saved semantic reference comparisons remain visible separately from accepted evaluation projections',()=>{
 assert.deepEqual(savedSemanticResults([{evaluations:[{evaluator_kind:'fixture'}],agent_assessments:[{driver_kind:'semantic',comparison_only:true,structured_result:{assessment:{proposed_disposition:'monitor'}}},{driver_kind:'semantic',comparison_only:true,structured_result:{}},{driver_kind:'scripted',comparison_only:true,structured_result:{assessment:{}}}]}]),{evaluations:0,comparisons:1});
});
