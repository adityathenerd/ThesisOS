import test from 'node:test';
import assert from 'node:assert/strict';
import {observeTask} from '../src/task-monitor.ts';
const task=status=>({id:'t1',mandate_id:'m1',status,type:'test',case_id:null,error:null,created_at:'2026-10-24T06:00:00Z',updated_at:'2026-10-24T06:01:00Z'});
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('monitor survives more than the former 40-poll limit, then emits completion once',async()=>{
 const queue=[],states=[];let reads=0,terminals=0;
 const stop=observeTask({taskId:'t1',mandateId:'m1',read:async()=>task(++reads<61?'running':'succeeded'),onTask:t=>states.push(t.status),onTerminal:()=>{terminals++},onError:e=>{throw e},schedule:cb=>{queue.push(cb);return queue.length},cancel:()=>{}});
 await tick();while(queue.length){queue.shift()();await tick()}
 assert.equal(reads,61);assert.equal(terminals,1);assert.equal(states.at(-1),'succeeded');stop();
});
test('stopping observation neither cancels backend work nor accepts a late response',async()=>{
 let resolve,seen=0;const response=new Promise(r=>resolve=r);
 const stop=observeTask({taskId:'t1',mandateId:'m1',read:()=>response,onTask:()=>seen++,onTerminal:()=>seen++,onError:()=>seen++});
 stop();resolve(task('succeeded'));await tick();assert.equal(seen,0);
});
test('a mismatched task is refused and a failed task remains a task failure',async()=>{
 const errors=[],terminal=[];
 observeTask({taskId:'t1',mandateId:'m1',read:async()=>({...task('running'),mandate_id:'other'}),onTask:()=>{},onTerminal:()=>{},onError:e=>errors.push(e.message)});
 observeTask({taskId:'t1',mandateId:'m1',read:async()=>({...task('failed'),error:'Model transport failed'}),onTask:()=>{},onTerminal:t=>terminal.push(t.status),onError:e=>errors.push(e.message)});
 await tick();assert.equal(errors.length,1);assert.match(errors[0],/does not match/);assert.deepEqual(terminal,['failed']);
});
