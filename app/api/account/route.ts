import { getChatGPTUser } from '../../chatgpt-auth';
export async function GET(){const user=await getChatGPTUser();return Response.json(user?{id:user.userId,name:user.fullName||user.email||'Your account'}:{id:null},{headers:{'Cache-Control':'no-store'}});}
