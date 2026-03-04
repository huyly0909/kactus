import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@kactus-bloom/ui': path.resolve(__dirname, '../bloom-ui/src'),
    },
  },
  server: {
    port: 17630,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:17600',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:17600',
        ws: true,
      },
    },
  },
  css: {
    postcss: {
      plugins: [],
    },
  },
});
