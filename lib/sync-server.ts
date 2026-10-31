import { canonicalRecord,validRecord } from './model';
export async function syncRequest(request:Request,userId:string|null,db:D1Database){
 const json=(value:unknown,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store'}});
 if(!userId)return json({error:'Sign in to sync your workouts.'},401);
 if(request.method==='POST'){
  const origin=request.headers.get('origin');if(!origin||origin!==new URL(request.url).origin)return json({error:'Invalid origin.'},403);
  if(Number(request.headers.get('content-length'))>1024*1024)return json({error:'Batch too large.'},413);
  const raw=await request.text();if(raw.length>1024*1024)return json({error:'Batch too large.'},413);
  let body;try{body=JSON.parse(raw)}catch{return json({error:'Invalid JSON.'},400)}
  if(!Array.isArray(body.records)||body.records.length>50||!body.records.every(validRecord))return json({error:'Invalid workout data.'},400);
  const records=body.records.map(canonicalRecord);
  // Immutable records make retries safe and avoid overwriting another device's history.
  if(records.length)await db.batch(records.map((r:any)=>db.prepare('INSERT INTO entries(user_id,record_id,kind,payload,created_at) VALUES(?,?,?,?,?) ON CONFLICT(user_id,record_id) DO NOTHING').bind(userId,r.id,r.kind,JSON.stringify(r),new Date().toISOString())));
  return json({ack:records.map((r:any)=>r.id)});
 }
 const cursor=Number(new URL(request.url).searchParams.get('cursor')||0);if(!Number.isSafeInteger(cursor)||cursor<0)return json({error:'Invalid cursor.'},400);
 const result=await db.prepare('SELECT sequence,payload FROM entries WHERE user_id=? AND sequence>? ORDER BY sequence ASC LIMIT 200').bind(userId,cursor).all<{sequence:number;payload:string}>();
 return json({records:result.results.map(r=>JSON.parse(r.payload)),cursor:result.results.at(-1)?.sequence??cursor,more:result.results.length===200});
}
