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
  build: {
    rollupOptions: {
      output: {
        // Split long-lived vendor code into stable chunks so it caches across
        // deploys, separate from per-route app chunks (React.lazy) and each other.
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'query-vendor': ['@tanstack/react-query', '@tanstack/react-table'],
          'radix-vendor': [
            '@radix-ui/react-dialog',
            '@radix-ui/react-select',
            '@radix-ui/react-label',
            '@radix-ui/react-slot',
          ],
          'i18n-vendor': ['i18next', 'react-i18next'],
        },
      },
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
