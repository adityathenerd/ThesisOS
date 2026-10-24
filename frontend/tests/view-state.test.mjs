import test from 'node:test';
import assert from 'node:assert/strict';
import {readView,viewHash} from '../src/view-state.ts';

test('the initial workspace is the dashboard and cases use a focused reloadable route',()=>{
 assert.deepEqual(readView(''),{view:'dashboard',caseId:null});
 assert.deepEqual(readView('#unknown'),{view:'dashboard',caseId:null});
 assert.deepEqual(readView(viewHash('cases','case/a #1')),{view:'cases',caseId:'case/a #1'});
 assert.deepEqual(readView(viewHash('cases')),{view:'cases',caseId:null});
 assert.deepEqual(readView('#reference'),{view:'reference',caseId:null});
 assert.deepEqual(readView('#mandate'),{view:'mandate',caseId:null});
});
test('invalid case links safely open the collection',()=>{
 assert.deepEqual(readView('#cases/%E0%A4%A'),{view:'cases',caseId:null});
 assert.deepEqual(readView('#cases/'),{view:'cases',caseId:null});
});
