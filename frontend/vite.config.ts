import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'public',
      filename: 'sw.js',
      injectManifest: {
        injectionPoint: '__WB_MANIFEST',
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
      },
      manifest: false,
      devOptions: {
        enabled: true,
        type: 'module',
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5273,
    proxy: {
      // All API calls use /api/v1 prefix — proxy through nginx reverse proxy.
      // The backend container port (8010) is intentionally not exposed to the
      // host; all traffic routes through nginx on port 8080.
      '/api/v1': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/main.tsx',
        'src/sw.ts',
        'src/registerSW.ts',
        'src/vite-env.d.ts',
        'src/**/*.d.ts',
        'src/test/**',
      ],
    },
  },
});
