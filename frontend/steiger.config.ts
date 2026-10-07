import fsd from '@feature-sliced/steiger-plugin';
import { defineConfig } from 'steiger';

/** Проверка архитектуры FSD: слои, публичные API слайсов, кросс-импорты. Сгенерированный клиент и тесты исключены. */
export default defineConfig([
  ...fsd.configs.recommended,
  { ignores: ['**/generated/**', '**/test/**', '**/*.test.ts', '**/*.test.tsx'] },
]);
