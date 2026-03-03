import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 8080,
    allowedHosts: ['tableaumcp.ubl.com.pk']
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
