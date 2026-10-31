import {spawnSync} from 'node:child_process';import {mkdirSync,writeFileSync} from 'node:fs';
mkdirSync('.sites-runtime/testbuild',{recursive:true});writeFileSync('.sites-runtime/testbuild/package.json','{"type":"commonjs"}');
for(const args of [['node_modules/typescript/bin/tsc','lib/model.ts','lib/sync-server.ts','--outDir','.sites-runtime/testbuild','--module','commonjs','--target','es2022','--skipLibCheck','--types','node,@cloudflare/workers-types'],['--test','tests/core.test.mjs']]){const r=spawnSync(process.execPath,args,{stdio:'inherit'});if(r.status!==0)process.exit(r.status??1)}
