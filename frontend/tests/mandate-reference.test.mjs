import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {localReferenceMeta,thesisSections,referenceHash,verifyReference} from '../src/mandate-reference.ts';

const source=fs.readFileSync(new URL('../src/reference/scouting-mandate-v0.3.md',import.meta.url),'utf8');
test('canonical review contains all eleven complete sections and preserves source identity',async()=>{
 const result=thesisSections(source);assert.equal(result.sections.length,11);assert.match(result.sections.find(s=>s.id==='4').text,/contribution/i);assert.match(result.sections.find(s=>s.id==='9').text,/human/i);assert.match(result.sections.find(s=>s.id==='11').text,/YC/i);assert.equal(source.length,23728);assert.equal(await referenceHash(source),localReferenceMeta.document_sha256);assert.equal(await verifyReference({...localReferenceMeta,document_text:source}),true);
});
test('a document hash is not accepted for a changed or shortened reference',async()=>{
 assert.equal(await verifyReference({...localReferenceMeta,document_text:source.slice(0,900)}),false);
 assert.equal(await verifyReference({...localReferenceMeta,document_sha256:'invalid',document_text:source}),false);
});
