import test from 'node:test';
import assert from 'node:assert/strict';
import {scoutingUsage,readScoutingRun,activeScoutingRun} from '../src/scouting-run.ts';
const run=()=>({id:'saved-run',status:'running',deadline:'2026-10-24T12:00:00Z',limits:{max_new_cases:4,max_provider_requests:20,max_credits:50,max_model_assessments:4},attempts:[{kind:'provider',quoted_microcredits:3000000,actual_microcredits:null},{kind:'provider',quoted_microcredits:2000000,actual_microcredits:1500000},{kind:'model',quoted_microcredits:0,actual_microcredits:null}],candidates:[{key:'same',case_id:'new-case'},{key:'same',case_id:'new-case'}],completed_case_ids:['new-case']});
test('unknown provider use retains its reservation and never becomes zero confirmed spend',()=>{
 const r=readScoutingRun(run()),usage=scoutingUsage(r);assert.equal(usage.confirmedCredits,1.5);assert.equal(usage.reservedCredits,3);assert.equal(usage.unknownReceipts,1);assert.equal(usage.providerAttempts,2);assert.equal(usage.modelAttempts,1);
});
test('encounters do not duplicate saved case counts and stop requests remain active until acknowledged',()=>{
 const r=run();assert.equal(scoutingUsage(r).newCases,1);assert.equal(scoutingUsage(r).completeCases,1);assert.equal(activeScoutingRun({...r,status:'stopping'}),true);assert.equal(activeScoutingRun({...r,status:'stopped'}),false);assert.throws(()=>readScoutingRun({...r,status:'invented'}),/Unsupported/);
});
