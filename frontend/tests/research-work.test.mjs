import test from 'node:test';
import assert from 'node:assert/strict';
import {workLabel,readResearchWork,observedResearchTasks} from '../src/research-work.ts';
const item={id:'case',version:3,company_name:'Saved company'};
const ref={case_id:'case',case_version:3,thesis_version:1,policy_version:1,evidence_hash:'saved-hash'};
function response(){return {case_id:'case',case_version:3,assessment_id:'assessment',assessment_current:true,workflow:{state:'human_research_required',explanation:'A decisive question remains.',input_ref:ref,assessment_input_ref:ref,assessment_ref:'assessment',active_task_ids:[],human_research_points:[{question_id:'current',question:'Can the result be repeated?',what_to_obtain:'A worked demonstration',decision_consequence:'Decides whether the core is repeatable',why_agent_stopped:'Public sources did not answer it',attempted_task_ids:['attempt']}],task_intents:[{kind:'investigate_claim'}]},attempts:[{task_id:'historical',question_id:'resolved',status:'succeeded',summary:'Resolved former question',accepted_evidence_ids:['saved'],source_urls:[],attempted_at:'2026-10-24T08:00:00Z'},{task_id:'attempt',question_id:'current',status:'no_answer',summary:'Inspected product documentation',accepted_evidence_ids:[],source_urls:['https://example.com/product'],attempted_at:'2026-10-24T09:00:00Z'}]};}
test('missing work or a pursue proposal cannot become reported execution',()=>{
 assert.equal(workLabel(null,'case',3),'Next-step execution not reported');
 const work=readResearchWork(response(),item);assert.deepEqual(observedResearchTasks({case:work},[item]),[]);
});
test('case, factual snapshot and assessment boundaries refuse stale readiness',()=>{
 const data=response(),work=readResearchWork(data,item,'assessment');
 assert.equal(workLabel(work,'case',3),'Human research needed');
 assert.equal(workLabel(work,'other',3),'Work status needs refresh');
 assert.equal(workLabel(work,'case',4),'Work status needs refresh');
 assert.equal(readResearchWork(data,item,'new-assessment').current,false);
 assert.equal(readResearchWork({...data,assessment_current:false},item).current,false);
 data.workflow.assessment_input_ref={...ref,evidence_hash:'old'};assert.equal(readResearchWork(data,item).current,false);
});
test('current human questions keep their own failed attempts while resolved history stays separate',()=>{
 const work=readResearchWork(response(),item);
 assert.equal(work.human_questions.length,1);assert.deepEqual(work.human_questions[0].attempts,['Inspected product documentation (no answer)']);assert.equal(work.attempts.length,2);assert.equal(work.human_questions[0].why_stopped,'Public sources did not answer it');
});
test('only explicit current queued/running task IDs appear in active work',()=>{
 const data=response();data.workflow.state='actively_researching';data.workflow.active_task_ids=['attempt','historical'];data.attempts[1].status='running';
 const work=readResearchWork(data,item);assert.deepEqual(observedResearchTasks({case:work},[item]).map(t=>t.id),['attempt']);
 assert.deepEqual(observedResearchTasks({case:work},[{...item,version:4}]),[]);
 data.workflow.state='research_required';assert.deepEqual(observedResearchTasks({case:readResearchWork(data,item)},[item]),[]);
});
test('new evidence may truthfully require reassessment while the last assessment is stale',()=>{
 const data=response();data.assessment_current=false;data.workflow.state='reassessment_required';data.workflow.assessment_input_ref={...ref,case_version:2,evidence_hash:'historical'};
 const work=readResearchWork(data,item);assert.equal(work.current,true);assert.equal(workLabel(work,item.id,item.version),'Reassessment needed');assert.deepEqual(observedResearchTasks({case:work},[item]),[]);
});
test('an optional specialist evidence packet does not upgrade human research or qualification',()=>{
 const data=response();data.available_review_packet={kind:'specialist_evidence_review',label:'Specialist evidence review requested; company-capability linkage unresolved.',formal_partner_review_ready:false,qualification_accepted:false,evidence_ids:['saved'],interpretation_source:'saved interpretation'};
 const work=readResearchWork(data,item);assert.equal(work.state,'human_research_required');assert.equal(workLabel(work,item.id,item.version),'Human research needed');assert.equal(work.review_packet.label,data.available_review_packet.label);
 data.available_review_packet.qualification_accepted=true;assert.equal(readResearchWork(data,item).review_packet,null);
});
