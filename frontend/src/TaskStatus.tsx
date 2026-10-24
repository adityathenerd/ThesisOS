import {useEffect,useState} from 'react';
import {Check,Clock3,Loader2,RefreshCw,TriangleAlert} from 'lucide-react';
import type {Task} from './types';
import {isTaskActive} from './task-monitor';

export default function TaskStatus({task,loading,error,onRefresh}:{task:Task|null;loading:boolean;error:string;onRefresh:()=>void}){
 const [now,setNow]=useState(()=>Date.now());
 const active=isTaskActive(task);
 useEffect(()=>{if(!active)return;setNow(Date.now());const interval=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(interval)},[active,task?.id]);
 if(!task&&!loading&&!error)return null;
 const age=task?Math.max(0,Math.floor(((active?now:new Date(task.updated_at).getTime())-new Date(task.created_at).getTime())/1000)):null;
 const title=error?'Task status unavailable':loading&&!task?'Checking saved task':task?.status==='failed'?'Backend task failed':task?.status==='succeeded'?'Backend task completed':task?.status==='pending'?'Queued by backend':'Waiting for backend completion';
 return <section className={`task-status ${error||task?.status==='failed'?'failed':active?'waiting':'completed'}`} aria-label="Backend task status" role={error||task?.status==='failed'?'alert':'region'}><span className="task-status-symbol">{error||task?.status==='failed'?<TriangleAlert size={18}/>:active||loading?<Loader2 className="spin" size={18}/>:<Check size={18}/>}</span><div><div className="row wrap"><strong>{title}</strong>{task&&<span className="badge">{task.status}</span>}</div><p>{error||(task?.status==='failed'?task.error??'The backend reported an operational failure.':active?'Only the reported task state is shown. Detailed step progress and completion time are not reported.':'Review the saved result type. A completed task is not human qualification or a sent message.')}</p>{task&&<div className="task-status-meta"><span>{task.type.replaceAll('_',' ')}</span><span><Clock3 size={11}/>{Number.isFinite(age)?`${age}s task age`:'Task age unknown'}</span><span>Last report {new Date(task.updated_at).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</span></div>}{(error||task?.status==='failed')&&<p className="task-status-recovery">Refresh saved results before retrying an action. An operational failure is separate from an investment rejection.</p>}</div><button className="secondary" onClick={onRefresh} disabled={loading}><RefreshCw size={13}/>Refresh status</button></section>;
}
