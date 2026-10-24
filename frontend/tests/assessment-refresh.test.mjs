import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeAssessmentRevisions,latestAssessmentId} from '../src/assessment-refresh.ts';

test('a new assessment at the same factual version changes the refresh token once',()=>{
 const old={case:'assessment-old'},work={case_id:'case',case_version:3,current:true,assessment_id:'assessment-new'};
 const next=mergeAssessmentRevisions(old,{case:work});assert.notEqual(next,old);assert.equal(next.case,'assessment-new');
 assert.equal(mergeAssessmentRevisions(next,{case:work}),next);
 assert.equal(mergeAssessmentRevisions(next,{}),next);
 assert.equal(mergeAssessmentRevisions(next,{case:{...work,current:false,assessment_id:'stale'}}),next);
});
test('graph dependency follows the newest loaded assessment even when factual version is unchanged',()=>{
 const old={version:3,agent_assessments:[{id:'old',created_at:'2026-10-24T09:00:00Z',input_current:false}]};
 assert.equal(latestAssessmentId(old),'old');
 assert.equal(latestAssessmentId({...old,agent_assessments:[{id:'new',created_at:'2026-10-24T10:00:00Z',input_current:true},...old.agent_assessments]}),'new');
 assert.equal(latestAssessmentId(null),null);
});
