export const READ_TIMEOUT_MS=12_000;
export const SYNC_ASSESSMENT_TIMEOUT_MS=150_000;

export class ApiError extends Error{
 status:number|null;
 code:string;
 completionUnknown:boolean;
 constructor(message:string,status:number|null,code:string,completionUnknown=false){
  super(message);this.name='ApiError';this.status=status;this.code=code;this.completionUnknown=completionUnknown;
 }
}
type Options={body?:unknown;timeoutMs?:number;fetcher?:typeof fetch};
export async function requestJson<T>(base:string,path:string,options:Options={}):Promise<T>{
 const mutation=options.body!==undefined;
 const controller=new AbortController();
 const timer=setTimeout(()=>controller.abort(),options.timeoutMs??READ_TIMEOUT_MS);
 try{
  const response=await(options.fetcher??fetch)(base.replace(/\/$/,'')+path,{
   method:mutation?'POST':'GET',headers:mutation?{'Content-Type':'application/json'}:undefined,
   body:mutation?JSON.stringify(options.body):undefined,signal:controller.signal,
  });
  const payload=await response.json().catch(()=>null);
  if(!response.ok)throw new ApiError(payload?.error?.message??`Backend returned HTTP ${response.status}. Refresh saved state before retrying an action.`,response.status,payload?.error?.code??'http_error',mutation&&response.status>=500);
  if(payload===null)throw new ApiError('Backend returned an unreadable response. Refresh saved state before repeating an action.',response.status,'unreadable_response',mutation);
  return payload as T;
 }catch(e){
  if(e instanceof ApiError)throw e;
  if((e instanceof Error&&e.name==='AbortError')||controller.signal.aborted){
   if(mutation)throw new ApiError('The browser stopped waiting. Request completion is unknown and the backend may still finish. No action was retried. Refresh saved cases and task status before submitting again.',null,'request_timeout',true);
   throw new ApiError('The backend did not respond in time. Its work may still be running. Refresh task status or check the backend connection; no fixture fallback was used.',null,'request_timeout');
  }
  if(e instanceof TypeError){
   if(mutation)throw new ApiError(`Connection to ${base} was interrupted. The action may have reached the backend; completion is unknown. Refresh saved state before submitting again. No action was retried.`,null,'connection_error',true);
   throw new ApiError(`Cannot reach the backend at ${base}. Check the local service, API address and CORS, then refresh. No fixture fallback was used.`,null,'connection_error');
  }
  throw e;
 }finally{clearTimeout(timer)}
}
