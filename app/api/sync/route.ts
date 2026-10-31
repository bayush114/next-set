import { env } from 'cloudflare:workers';
import { getChatGPTUser } from '../../chatgpt-auth';
import { syncRequest } from '../../../lib/sync-server';
async function handle(request:Request){const user=await getChatGPTUser();if(!env.DB)return Response.json({error:'Storage unavailable; your changes remain saved locally.'},{status:503});try{return await syncRequest(request,user?.userId??null,env.DB)}catch{return Response.json({error:'Sync unavailable; retry shortly.'},{status:503,headers:{'Cache-Control':'no-store'}})}}
export const GET=handle;export const POST=handle;
