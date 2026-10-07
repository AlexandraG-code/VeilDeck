import { defineConfig } from 'orval';

/** Генерация типов и хуков TanStack Query из docs/api/openapi.json (руками src/api/generated не правится). */
export default defineConfig({
  veildeck: {
    input: '../docs/api/openapi.json',
    output: {
      mode: 'tags-split',
      target: 'src/api/generated',
      schemas: 'src/api/generated/model',
      client: 'react-query',
      override: {
        mutator: { path: 'src/shared/api/client.ts', name: 'apiClient' },
      },
    },
  },
});
