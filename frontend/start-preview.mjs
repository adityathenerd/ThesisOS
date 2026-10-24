import { realpathSync } from 'node:fs';
process.chdir(realpathSync.native(process.cwd()));
const { preview } = await import('vite');
const server = await preview({preview:{host:'127.0.0.1',port:5173,strictPort:true}});
server.printUrls();
