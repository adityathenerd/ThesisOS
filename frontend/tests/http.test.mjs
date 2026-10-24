import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiError,requestJson,SYNC_ASSESSMENT_TIMEOUT_MS} from '../src/http.ts';

test('mutation timeout leaves completion unknown and never retries the action',async()=>{
 let calls=0;
 const fetcher=async(_url,options)=>{calls++;return new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError'))))};
 await assert.rejects(requestJson('http://test.local','/signal',{body:{},timeoutMs:5,fetcher}),error=>error instanceof ApiError&&error.code==='request_timeout'&&error.completionUnknown&&/No action was retried/.test(error.message));
 assert.equal(calls,1);
 assert(SYNC_ASSESSMENT_TIMEOUT_MS>90_000);
});
test('stale conflict is retained as a backend refusal, not rewritten as network failure',async()=>{
 const fetcher=async()=>new Response(JSON.stringify({error:{code:'stale_version',message:'Assessment is stale. Refresh first.'}}),{status:409});
 await assert.rejects(requestJson('http://test.local','/review',{body:{},fetcher}),error=>error instanceof ApiError&&error.status===409&&error.code==='stale_version'&&!error.completionUnknown);
});
test('a mutation 500 can coexist with saved observations and requires a refresh',async()=>{
 const fetcher=async()=>new Response(JSON.stringify({error:{code:'internal_error',message:'Reassessment failed.'}}),{status:500});
 await assert.rejects(requestJson('http://test.local','/signal',{body:{},fetcher}),error=>error.completionUnknown&&error.code==='internal_error');
});
