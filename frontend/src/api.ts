import type { Case, CaseDetail, ConfigStatus, CreateMandate, Evaluation, Mandate, ReplayTemplate, SignalInput, Task, Transport, ResearchBatch } from './types';
import type {ScoutingRun} from './scouting-run';
import { fixtures } from './fixtures';
import {requestJson,SYNC_ASSESSMENT_TIMEOUT_MS} from './http';
type Env={VITE_API_URL?:string;VITE_TRANSPORT?:string};
const env=(import.meta as ImportMeta & {env:Env}).env;
export type TransportMode='http'|'fixture';
export const initialMode=():TransportMode=>(localStorage.getItem('thesisos-transport')??env.VITE_TRANSPORT)==='fixture'?'fixture':'http';
export const initialUrl=()=>localStorage.getItem('thesisos-api-url')??env.VITE_API_URL??'http://127.0.0.1:8000';
export function transport(mode:TransportMode,base:string):Transport {
 if(mode==='fixture')return fixtures;
 function request<T>(path:string,body?:unknown,timeoutMs?:number):Promise<T>{return requestJson<T>(base,path,{body,timeoutMs})}

 const items=async<T>(path:string)=>(await request<{items:T[]}>(path)).items;
 return {followThroughStages:id=>items<unknown>(`/api/v1/scouting-runs/${encodeURIComponent(id)}/follow-through`),stopFollowThroughStage:id=>request(`/api/v1/follow-through-stages/${encodeURIComponent(id)}/stop`,{}),scoutingRuns:()=>items<ScoutingRun>('/api/v1/scouting-runs'),startScoutingRun:input=>request<ScoutingRun>('/api/v1/scouting-runs',input),stopScoutingRun:id=>request<ScoutingRun>(`/api/v1/scouting-runs/${encodeURIComponent(id)}/stop`,{}),preOutreachReview:id=>request(`/api/v1/cases/${encodeURIComponent(id)}/pre-outreach-review`),researchFollowUp:id=>request(`/api/v1/cases/${encodeURIComponent(id)}/research-follow-up`),mandateReference:id=>request(`/api/v1/mandates/${encodeURIComponent(id)}/reference`),researchBatches:()=>items<ResearchBatch>('/api/v1/research-batches'),researchGraph:id=>request(`/api/v1/cases/${encodeURIComponent(id)}/research-graph`),replayTemplates:()=>items<ReplayTemplate>('/api/v1/fixtures/signals'),health:()=>request('/health'),config:()=>request<ConfigStatus>('/api/v1/config/status'),mandates:()=>items<Mandate>('/api/v1/mandates'),create:(v:CreateMandate)=>request<Mandate>('/api/v1/mandates',v),mandate:id=>request<Mandate>(`/api/v1/mandates/${encodeURIComponent(id)}`),run:id=>request<Task>(`/api/v1/mandates/${encodeURIComponent(id)}/run`,{}),cases:id=>items<Case>(`/api/v1/mandates/${encodeURIComponent(id)}/cases`),detail:id=>request<CaseDetail>(`/api/v1/cases/${encodeURIComponent(id)}`),evaluations:id=>items<Evaluation>(`/api/v1/cases/${encodeURIComponent(id)}/evaluations`),signal:(id,v:SignalInput)=>request<CaseDetail>(`/api/v1/cases/${encodeURIComponent(id)}/signals`,v,SYNC_ASSESSMENT_TIMEOUT_MS),task:id=>request<Task>(`/api/v1/tasks/${encodeURIComponent(id)}`)};
}
