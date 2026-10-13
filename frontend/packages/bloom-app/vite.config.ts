import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

// Set in the dev container (see deploy/dev/docker-compose.yml). On the host
// every branch below falls back to vite's normal defaults.
const inDocker = !!process.env.VITE_DOCKER;
// Host: kactus-fin on localhost. Container: reach it by compose service name.
const apiTarget = process.env.VITE_PROXY_TARGET || 'http://localhost:17600';

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
          // Charts are heavy and only reached from the market routes.
          'chart-vendor': ['recharts'],
        },
      },
    },
  },
  server: {
    port: 17630,
    // In the dev container: no browser to open, listen on all interfaces so the
    // host can reach it, and poll for file changes (bind-mount fs events are
    // not always delivered to the container). On the host these are vite defaults.
    open: !inDocker,
    host: inDocker || undefined,
    watch: inDocker ? { usePolling: true } : undefined,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: apiTarget.replace(/^http/, 'ws'),
        ws: true,
      },
    },
  },
});
