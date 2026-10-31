import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
const require=createRequire(import.meta.url);
const {validRecord,mergeRecords,suggestion,nextExercises,dailyVolume}=require('../.sites-runtime/testbuild/model.js');
const {syncRequest}=require('../.sites-runtime/testbuild/sync-server.js');
const exercise={id:'e1',name:'Bench',target:10,increment:5,sets:[{weight:100,reps:10,done:true},{weight:100,reps:10,done:true}]};
const record={id:'s1',kind:'session',date:'2026-10-30T18:00:00Z',name:'Push',exercises:[exercise]};
function db(){
 const sql=new DatabaseSync(':memory:');
 sql.exec(readFileSync(new URL('../drizzle/0000_chilly_tag.sql',import.meta.url),'utf8'));
 return {
  prepare(query){
   return {bind(...args){
    return {run:()=>sql.prepare(query).run(...args),all:async()=>({results:sql.prepare(query).all(...args)})};
   }};
  },
  async batch(statements){
   sql.exec('BEGIN');
   try{const result=statements.map(s=>s.run());sql.exec('COMMIT');return result}
   catch(e){sql.exec('ROLLBACK');throw e}
  }
 };
}
const post=records=>new Request('https://next-set.test/api/sync',{method:'POST',headers:{origin:'https://next-set.test','Content-Type':'application/json'},body:JSON.stringify({records})});
const get=(cursor=0)=>new Request('https://next-set.test/api/sync?cursor='+cursor);
test('validates records and rejects malformed sets',()=>{assert.ok(validRecord(record));assert.ok(!validRecord({...record,exercises:[{...exercise,sets:[{weight:-1,reps:10,done:true}]}]}));assert.ok(!validRecord({...record,date:'bad'}));assert.ok(!validRecord({id:'x',kind:'weight',date:record.date,weight:Infinity}))});
test('progression requires every planned set and does not mutate history',()=>{assert.equal(suggestion(exercise).weight,105);const incomplete={...exercise,sets:[...exercise.sets,{weight:100,reps:10,done:false}]};assert.equal(suggestion(incomplete).increase,false);assert.equal(suggestion({...exercise,sets:[{weight:100,reps:9,done:true}]}).increase,false);const next=nextExercises([exercise],true);assert.equal(next[0].sets[0].weight,105);assert.equal(next[0].sets[0].done,false);assert.equal(exercise.sets[0].weight,100)});
test('merge and volume only count unique completed sessions',()=>{const records=mergeRecords([record],[record]);assert.equal(records.length,1);assert.equal(dailyVolume(records)[0].value,2000)});
test('API rejects anonymous writes and cross-origin submissions',async()=>{const store=db();assert.equal((await syncRequest(post([record]),null,store)).status,401);assert.equal((await syncRequest(new Request('https://next-set.test/api/sync',{method:'POST',body:'{}',headers:{origin:'https://evil.test'}}),'u1',store)).status,403)});
test('retrying writes is idempotent, read cursors work, users stay isolated',async()=>{const store=db();assert.equal((await syncRequest(post([record]),'u1',store)).status,200);await syncRequest(post([record]),'u1',store);const first=await(await syncRequest(get(),'u1',store)).json();assert.equal(first.records.length,1);assert.equal((await(await syncRequest(get(),'u2',store)).json()).records.length,0);assert.equal((await(await syncRequest(get(first.cursor),'u1',store)).json()).records.length,0);await syncRequest(post([{...record,id:'s2'}]),'u1',store);assert.equal((await(await syncRequest(get(first.cursor),'u1',store)).json()).records[0].id,'s2');await syncRequest(post([record]),'u2',store);assert.equal((await(await syncRequest(get(),'u2',store)).json()).records.length,1)});
test('rejects malformed batches without writing partial data',async()=>{const store=db();assert.equal((await syncRequest(post([record,{bad:true}]),'u1',store)).status,400);assert.equal((await(await syncRequest(get(),'u1',store)).json()).records.length,0)});
