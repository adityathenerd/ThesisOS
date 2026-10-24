import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { realpathSync } from 'node:fs';
// Resolve the Desktop junction once so Vite and esbuild use the same file identity.
export default defineConfig({ root: realpathSync.native(process.cwd()), plugins: [react()] });
