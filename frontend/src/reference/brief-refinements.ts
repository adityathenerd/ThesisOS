import type {CaseBrief} from '../case-brief';

// Plain-language editorial views of two saved assessments, never replacement evidence.
// The unedited agent brief and reasoning remain under Sources & analysis / History.
export function refineSavedBrief(brief:CaseBrief,binding?:{thesis_version?:number;policy_version?:number;evidence_hash?:string}):CaseBrief{
 const samePolicy=binding?.thesis_version===1&&binding.policy_version===1;
 if(samePolicy&&binding?.evidence_hash==='ff1f32bcb5e3d5bab2822e29e5de9b40853078e6824a6fb75ffddbdead1a9473'&&brief.case_id==='case_5a0be0c7b23d4f3da9b1edfa8629e09b'&&brief.case_version===2&&brief.assessment_id==='assessment_a9b61d833f5d468d83c5ca1e2e35deda')return{
  ...brief,origin:'editorial_saved_evidence',
  business:{...brief.business,text:'Aphotic Bio uses computer models of DNA changes to look for potential drug targets in chronic disease.'},
  recommendation:{...brief.recommendation,text:'Pursue one experimental report to test whether its computer-predicted targets actually change disease biology.'},
  founder_signals:brief.founder_signals.map(signal=>({...signal,contribution:'Named author of public DIS+ code; the company credits her doctoral work as DISCERN’s origin.',relevance:'Connects attributable computational work to the company’s drug-target search.',limitation:'Code was inspected, not run. Experimental validation and commercial rights remain unverified.'})),
  decisive_doubt:{...brief.decisive_doubt,text:'Do the predicted targets produce a useful biological effect? No program-linked experiment was inspected.'},
  next_action:{...brief.next_action,text:'Inspect an authorized report for one named program: check experimental controls, who did the work, and access rights.'},
  material_caveats:['Computer predictions are hypotheses, not experimental validation or demonstrated treatment benefit.'],
 };
 if(samePolicy&&binding?.evidence_hash==='665a406a42dfa5e47f0ed55d3825d14b44ce48c36dfcaa5948ddf50b7f8e2ea0'&&brief.case_id==='case_d57d6d50977a4652b98272704449804d'&&brief.case_version===2&&brief.assessment_id==='assessment_c5112e389ea14cee88833f8bae3fddf9')return{
  ...brief,origin:'editorial_saved_evidence',
  business:{...brief.business,text:'careMESH builds NAVIGATE, software for hospital care teams to organize referrals and follow-up across fragmented manual workflows.'},
  recommendation:{...brief.recommendation,text:'Pursue a current workflow walkthrough: product screenshots and a named hospital implementation give concrete claims to verify.'},
  reasons:brief.reasons.map((reason,index)=>({...reason,text:index===0?'Product screenshots show pathways and sequenced tasks; software functionality was not exercised.':'Company reports a Tampa General Hospital implementation in April 2021; current use and results remain unverified.'})),
  founder_signals:brief.founder_signals.map(signal=>({...signal,contribution:'Linked clinical coordination failures to the team’s design of NAVIGATE.',relevance:'Connects clinical problem experience to a specific product choice.',limitation:'Company article has attribution ambiguity; personal implementation ownership is unverified.'})),
  founder_unknown:'Current implementation ownership, Catherine Thomas’s contribution and customer access remain unverified.',
  decisive_doubt:{...brief.decisive_doubt,text:'Does the historical hospital rollout reflect a current working product with measurable benefit?'},
  next_action:{...brief.next_action,text:'Inspect a current referral-workflow walkthrough, identify who implemented it, and clarify the advertised reduction metric.'},
  material_caveats:['Static pages and screenshots were inspected. A 2021 deployment report does not establish current adoption or outcomes.'],
 };
 return brief;
}
