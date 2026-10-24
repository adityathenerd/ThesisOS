import { realpathSync } from 'node:fs';
// esbuild's output metadata is relative to cwd; normalize an NTFS junction before Vite loads.
process.chdir(realpathSync.native(process.cwd()));
const { createServer } = await import('vite');
const server = await createServer({server:{host:'127.0.0.1',port:5173,strictPort:true}});
await server.listen();
server.printUrls();
