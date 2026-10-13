import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, strictPort: true,
    proxy: { '/observer': { target: 'http://127.0.0.1:8810', changeOrigin: true } } },
  build: { sourcemap: false, commonjsOptions: { include: [/node_modules/, /evidence\.validator\.cjs/] } },
});
