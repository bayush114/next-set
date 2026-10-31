import { mergeRecords, type RecordEntry } from './model';
export type Cache={records:RecordEntry[];pending:string[];cursor:number};
const empty=():Cache=>({records:[],pending:[],cursor:0});
function database():Promise<IDBDatabase>{return new Promise((resolve,reject)=>{const req=indexedDB.open('next-set-offline',1);req.onupgradeneeded=()=>req.result.createObjectStore('accounts');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error)})}
export async function mutate(owner:string,fn:(cache:Cache)=>Cache):Promise<Cache>{const db=await database();return new Promise((resolve,reject)=>{const tx=db.transaction('accounts','readwrite'),store=tx.objectStore('accounts');let next:Cache;const req=store.get(owner);req.onsuccess=()=>{try{next=fn(req.result||empty());store.put(next,owner)}catch(e){tx.abort();reject(e)}};tx.oncomplete=()=>{db.close();resolve(next)};tx.onerror=()=>{db.close();reject(tx.error)};tx.onabort=()=>{db.close();reject(tx.error||new Error('Local save failed'))}})}
export const readCache=(owner:string)=>mutate(owner,c=>c);
export const addRecords=(owner:string,records:RecordEntry[])=>mutate(owner,c=>({...c,records:mergeRecords(c.records,records),pending:[...new Set([...c.pending,...records.map(r=>r.id)])]}));
export const acknowledge=(owner:string,ids:string[])=>mutate(owner,c=>({...c,pending:c.pending.filter(id=>!ids.includes(id))}));
export const receive=(owner:string,records:RecordEntry[],cursor:number)=>mutate(owner,c=>({...c,records:mergeRecords(c.records,records),cursor:Math.max(c.cursor,cursor)}));
