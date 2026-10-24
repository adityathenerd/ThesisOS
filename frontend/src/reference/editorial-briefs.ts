import type {CaseBrief} from '../case-brief';

// A read-only editorial view of existing observations and the saved assessment.
// It is intentionally pinned: any changed case, assessment or citation refuses reuse.
export const editorialBriefs:CaseBrief[]=[{
 case_id:'case_201e1de12eea4da49abc6f8de3317e5a',case_version:2,
 assessment_id:'assessment_960ba2c8c0c743e5aa12fc73e9d8dffd',origin:'editorial_saved_evidence',
 business:{text:'Nurture Bridge provides healthcare organizations with workflow consulting to improve referral handoffs.',evidence_ids:['evidence:nurture:problem-context','evidence:nurture:current-offering']},
 decision:'monitor',
 recommendation:{text:'Monitor until a worked deployment shows its referral-workflow methods can be reused beyond bespoke advice.',evidence_ids:['evidence:nurture:current-offering','evidence:nurture:founder-methods']},
 reasons:[
  {text:'The company attributes two named workflow methods to a founder with relevant healthcare-operations experience.',evidence_ids:['evidence:nurture:founder-methods','evidence:nurture:founder-background']},
  {text:'The current consulting offering does not yet demonstrate a differentiated, reusable product or asset.',evidence_ids:['evidence:nurture:current-offering','evidence:nurture:founder-methods']},
 ],
 founder_signals:[{person:'Sabina Ben Kasim',contribution:'Credited with creating Workflow-to-Value and Referral Reliability Bridge.',relevance:'The work directly addresses the referral-workflow problem.',source_strength:'Company-reported',limitation:'Execution, outcomes and work chronology remain unverified.',evidence_ids:['evidence:nurture:founder-role','evidence:nurture:founder-methods','evidence:nurture:founder-background']}],
 founder_unknown:null,
 decisive_doubt:{text:'Is there a differentiated, reusable asset—or only founder-led consulting?',evidence_ids:['evidence:nurture:founder-methods','evidence:nurture:current-offering']},
 next_action:{text:'Reopen on an accessible worked workflow or deployment showing the reusable component, intended user, baseline and founder contribution.',evidence_ids:['evidence:nurture:current-offering','evidence:nurture:founder-methods']},
 material_caveats:['The services page says it does not sell a proprietary software platform. No working artifact was inspected; exact buyer, stage and YC backing remain unknown.'],
}];
