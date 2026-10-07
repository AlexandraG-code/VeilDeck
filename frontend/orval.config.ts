import { defineConfig } from 'orval';

/** Генерация типов и хуков TanStack Query из docs/api/openapi.json (руками src/shared/api/generated не правится). */
export default defineConfig({
  veildeck: {
    input: '../docs/api/openapi.json',
    output: {
      mode: 'tags-split',
      target: 'src/shared/api/generated',
      schemas: 'src/shared/api/generated/model',
      client: 'react-query',
      httpClient: 'axios',
      override: {
        mutator: { path: 'src/shared/api/client.ts', name: 'apiClient' },
      },
    },
  },
});
