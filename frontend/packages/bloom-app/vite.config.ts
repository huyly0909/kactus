import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@modules': path.resolve(__dirname, './src/modules'),
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
});
