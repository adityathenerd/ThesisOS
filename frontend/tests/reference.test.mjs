import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {mandateStarter,researchExamples,tracks,referenceMarker} from '../src/reference.ts';

test('editable v0.3 starter fits the existing API and names all four proof tracks',()=>{
 assert(mandateStarter.length<=20000);
 assert(mandateStarter.includes(referenceMarker));
 assert.deepEqual(tracks.map(t=>t.id),['H','R','D','T']);
 for(const id of ['H','R','D','T'])assert(mandateStarter.includes(`${id} —`));
 assert(mandateStarter.includes('not YC-endorsed'));
 assert(mandateStarter.includes('Unknown is not zero'));
 assert(mandateStarter.includes('Agents recommend; a human approves qualification'));
 assert(!mandateStarter.includes('Whether human acceptance gates the headline readiness count remains unresolved'));
});
test('full primary source is preserved without API-limit truncation',async()=>{
 const primary=await readFile(new URL('../../planning/investment-thesis/scouting-mandate.md',import.meta.url));
 const snapshot=await readFile(new URL('../src/reference/scouting-mandate-v0.3.md',import.meta.url));
 assert.deepEqual(snapshot,primary);
 assert(primary.toString('utf8').length>20000);
});
test('research investigations and known YC reference retain different novelty boundaries',()=>{
 const biodock=researchExamples.find(c=>c.name==='Biodock');
 assert.equal(biodock.kind,'reference');
 assert(biodock.yc.startsWith('Known YC-backed'));
 for(const name of ['AlloDirect','MORF-Bio','Graph Therapeutics']){
  const example=researchExamples.find(c=>c.name===name);
  assert.equal(example.kind,'investigation');
  assert.equal(example.yc,'YC backing unknown');
  assert(example.gap&&example.next&&example.sources.length);
 }
 assert.equal(researchExamples.find(c=>c.name==='Graph Therapeutics').track,'T');
});
