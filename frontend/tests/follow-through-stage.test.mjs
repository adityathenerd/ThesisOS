import test from 'node:test';import assert from 'node:assert/strict';
import {readFollowThroughStage,caseFollowThrough,caseFollowThroughActive,followThroughLabel,scoutingUsage,publicPageAttempts} from '../src/scouting-run.ts';
const stage=()=>({id:'child',parent_run_id:'parent',stage_kind:'bounded_post_intake_followthrough',status:'running',deadline:'2026-10-24T11:23:21Z',updated_at:'2026-10-24T11:15:00Z',limits:{max_new_cases:0,max_provider_requests:8,max_credits:20,max_model_assessments:4,public_urls_per_case:2},attempts:[{intent:'public:case',kind:'public',status:'succeeded',quoted_microcredits:0,actual_microcredits:null,request:{case_id:'case',public_page_attempts:2}}],candidates:[{key:'company',case_id:'case',stage:'reassessing',research_state:'human_research_required'}],completed_case_ids:[]});
test('an actual child stage binds its parent and permits public attempts without inventing provider costs',()=>{
 const s=readFollowThroughStage(stage(),'parent');assert.equal(scoutingUsage(s).providerAttempts,0);assert.equal(scoutingUsage(s).unknownReceipts,0);assert.equal(publicPageAttempts(s),2);assert.throws(()=>readFollowThroughStage(s,'other'),/does not match/);
});
test('active reassessment remains visible instead of the earlier human handoff; untouched cases have no child status',()=>{
 const s=stage(),view=caseFollowThrough({child:s},'case');assert.equal(caseFollowThroughActive(view),true);assert.equal(followThroughLabel(view),'Reassessing');assert.equal(caseFollowThrough({child:s},'old-nine-case'),null);
 s.status='completed';s.candidates[0].stage='complete';assert.equal(followThroughLabel(caseFollowThrough({child:s},'case')),'Human handoff');s.candidates[0].research_state='monitor';assert.equal(followThroughLabel(caseFollowThrough({child:s},'case')),'Monitor');
});
test('stopped queued work is not presented as completed enrichment and external page quantities are counted',()=>{
 const s=stage();s.status='stopped';s.candidates[0].stage='queued';assert.equal(followThroughLabel(caseFollowThrough({child:s},'case')),'Enrichment stopped before attempt');
 s.attempts[0].request={external:{public_page_attempts:2}};assert.equal(publicPageAttempts(s),2);
});
