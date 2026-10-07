import react from '@vitejs/plugin-react';
import { URL, fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

const resolvePath = (path: string): string => fileURLToPath(new URL(path, import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@app': resolvePath('./src/app'),
      '@pages': resolvePath('./src/pages'),
      '@widgets': resolvePath('./src/widgets'),
      '@features': resolvePath('./src/features'),
      '@entities': resolvePath('./src/entities'),
      '@shared': resolvePath('./src/shared'),
      '@api': resolvePath('./src/api'),
    },
  },
  server: {
    proxy: { '/api': 'http://localhost:8080' },
  },
  test: {
    environment: 'happy-dom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
});
