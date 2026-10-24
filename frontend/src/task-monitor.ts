import type {Task} from './types';

type Options={taskId:string;mandateId:string;read:(id:string)=>Promise<Task>;onTask:(task:Task)=>void;onTerminal:(task:Task)=>void|Promise<void>;onError:(error:Error)=>void;intervalMs?:number;schedule?:(callback:()=>void,delay:number)=>ReturnType<typeof setTimeout>;cancel?:(timer:ReturnType<typeof setTimeout>)=>void};
export function isTaskActive(task:Task|null|undefined){return task?.status==='pending'||task?.status==='running'}
export function observeTask(options:Options){
 let stopped=false,timer:ReturnType<typeof setTimeout>|undefined;
 const schedule=options.schedule??setTimeout,cancel=options.cancel??clearTimeout;
 async function check(){
  try{
   const task=await options.read(options.taskId);
   if(stopped)return;
   if(task.id!==options.taskId||task.mandate_id!==options.mandateId)throw new Error('The returned task does not match this mandate and request. Refresh saved state.');
   options.onTask(task);
   if(isTaskActive(task))timer=schedule(check,options.intervalMs??1000);
   else await options.onTerminal(task);
  }catch(error){if(!stopped)options.onError(error instanceof Error?error:new Error('Task status unavailable.'))}
 }
 void check();
 return()=>{stopped=true;if(timer!==undefined)cancel(timer)};
}
