import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveBrief,validateBrief} from '../src/case-brief.ts';
import {editorialBriefs} from '../src/reference/editorial-briefs.ts';
import {refineSavedBrief} from '../src/reference/brief-refinements.ts';

const editorial=editorialBriefs[0];
const evidenceIds=[...new Set([editorial.business,editorial.recommendation,...editorial.reasons,editorial.decisive_doubt,editorial.next_action,...editorial.founder_signals].flatMap(claim=>claim.evidence_ids))];
const detail=()=>({id:editorial.case_id,version:2,company_name:'Nurture Bridge Marketing, LLC',evidence:evidenceIds.map(id=>({id})),agent_assessments:[{id:editorial.assessment_id,input_current:true,expected_case_version:2,created_at:'2026-10-24T07:33:22Z',structured_result:{assessment:{}}}]});
function wireDetail(){const record=detail();record.id='new-case';record.people=[{id:'person:saved-identity',name:'Saved researcher name',case_version:2}];record.agent_assessments=[{id:'new-assessment',input_current:true,expected_case_version:2,created_at:'2026-10-24T08:00:00Z',structured_result:{ref:{case_id:'new-case',case_version:2},assessment:{case_brief:{company_description:{text:'A sourced tool for a named user and task.',evidence_ids:[evidenceIds[0]]},research_posture:'pursue',main_reason:{text:'Inspect the worked result now because it could resolve repeatability.',evidence_ids:[evidenceIds[0]]},strongest_facts:[{text:'A worked result is attributed in the saved source.',evidence_ids:[evidenceIds[0]]}],founder_signals:[{person_id:'person:saved-identity',contribution:'Created the named worked tool.',relevance:'It addresses the research task.',evidence_ids:[evidenceIds[0]],source_strength:'first_party_claim'}],founder_unknowns:['Deployment and rights are unverified.'],decisive_doubt:{text:'Can another user repeat it?',evidence_ids:[evidenceIds[0]]},next_action:'Inspect a representative worked task.',future_trigger:null,operational_limitations:['No provider execution authorized by this display.']}}}}];return record;}

test('existing editorial case is concise, sourced, and describes consulting without inventing product execution',()=>{
 const result=resolveBrief(detail());assert.equal(result.status,'available');
 const brief=result.brief;assert.equal(brief.origin,'editorial_saved_evidence');assert.match(brief.business.text,/workflow consulting/);assert.equal(brief.decision,'monitor');assert.equal(brief.reasons.length,2);assert.match(brief.founder_signals[0].contribution,/Credited/);assert.equal(brief.founder_signals[0].source_strength,'Company-reported');
 const text=[brief.business.text,brief.recommendation.text,...brief.reasons.map(r=>r.text),...brief.founder_signals.flatMap(s=>[s.person,s.contribution,s.relevance,s.limitation]),brief.decisive_doubt.text,brief.next_action.text,...brief.material_caveats].join(' ');
 assert.ok(text.split(/\s+/).length<=200);
});
test('changed versions, a newer assessment, and unresolved citations cannot reuse an old concise brief',()=>{
 const version=detail();version.version=3;assert.equal(resolveBrief(version).status,'stale');
 const newer=detail();newer.agent_assessments.push({...newer.agent_assessments[0],id:'newer',created_at:'2026-10-24T08:00:00Z'});assert.equal(resolveBrief(newer).status,'stale');
 const missing=detail();missing.evidence=[];assert.equal(validateBrief(editorial,missing).status,'invalid');
});
test('published inline brief uses actual person identity and separates operational limits from investment meaning',()=>{
 const input=wireDetail(),result=resolveBrief(input);assert.equal(result.status,'available');assert.equal(result.brief.founder_signals[0].person,'Saved researcher name');assert.equal(result.brief.founder_signals[0].source_strength,'Company-reported');assert.equal(result.brief.founder_unknown,'Deployment and rights are unverified.');assert.deepEqual(result.brief.material_caveats,[]);assert.equal(result.brief.operational_limitations.length,1);assert.equal(result.brief.origin,'saved_agent_brief');
 delete input.people;assert.equal(resolveBrief(input).brief.founder_signals[0].person,'Contributor name not available');
});
test('unknown companies stay unknown, and monitors require a concrete trigger with valid source links',()=>{
 assert.equal(resolveBrief({...detail(),id:'company-name-is-not-evidence'}).status,'missing');
 const input=wireDetail(),brief=input.agent_assessments[0].structured_result.assessment.case_brief;brief.research_posture='monitor';assert.equal(resolveBrief(input).status,'invalid');brief.future_trigger='A representative worked task becomes available.';assert.equal(resolveBrief(input).status,'available');brief.strongest_facts[0].evidence_ids=['not-saved'];assert.equal(resolveBrief(input).status,'invalid');
});

test('editorial plain-language views require exact immutable assessment and full input binding',()=>{
 const brief={...editorial,case_id:'case_5a0be0c7b23d4f3da9b1edfa8629e09b',case_version:2,assessment_id:'assessment_a9b61d833f5d468d83c5ca1e2e35deda'};
 const binding={thesis_version:1,policy_version:1,evidence_hash:'ff1f32bcb5e3d5bab2822e29e5de9b40853078e6824a6fb75ffddbdead1a9473'};
 assert.equal(refineSavedBrief(brief),brief);
 assert.equal(refineSavedBrief(brief,{...binding,evidence_hash:'changed'}),brief);
 assert.equal(refineSavedBrief(brief,{...binding,policy_version:2}),brief);
 const changed={...brief,assessment_id:'newer-assessment'};assert.equal(refineSavedBrief(changed,binding),changed);
 const refined=refineSavedBrief(brief,binding);assert.match(refined.business.text,/computer models of DNA changes/);assert.deepEqual(refined.business.evidence_ids,brief.business.evidence_ids);assert.equal(refined.origin,'editorial_saved_evidence');
});
