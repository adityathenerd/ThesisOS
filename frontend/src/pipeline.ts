import type {Case,CaseStatus} from './types';

export const pipelineStages: {id:string;name:string;description:string;statuses:CaseStatus[];tone:string}[] = [
 {id:'discovery',name:'Discovered',description:'New companies in the radar',statuses:['discovered'],tone:'slate'},
 {id:'research',name:'Researching',description:'Enrichment and investigation',statuses:['enrichment_pending','investigating'],tone:'blue'},
 {id:'evidence',name:'Needs evidence',description:'Material claims to resolve',statuses:['needs_evidence'],tone:'amber'},
 {id:'monitor',name:'Monitoring',description:'Waiting for a useful signal',statuses:['monitor'],tone:'blue'},
 {id:'qualified',name:'Qualified',description:'Fit established; handoff incomplete',statuses:['qualified'],tone:'green'},
 {id:'ready',name:'Outreach ready',description:'A package to review',statuses:['outreach_ready'],tone:'green'},
 {id:'closed',name:'Closed',description:'Rejected or failed cases',statuses:['rejected','failed'],tone:'slate'},
];
export const matchesFilter=(c:Case,filter:string)=>filter==='all'||(filter.startsWith('stage:')?pipelineStages.find(s=>`stage:${s.id}`===filter)?.statuses.includes(c.status)??false:c.status===filter);
