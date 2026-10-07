import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

/** Слои FSD сверху вниз: слой может импортировать только нижележащие. */
const LAYERS = ['app', 'pages', 'widgets', 'features', 'entities', 'shared'];
const SLICE_LAYERS = ['pages', 'widgets', 'features', 'entities'];

/**
 * Правила no-restricted-imports для слоя: запрет импорта вышележащих слоёв.
 * @param {string} layer имя слоя
 */
const layerRule = (layer) => {
  const above = LAYERS.slice(0, LAYERS.indexOf(layer));

  return {
    files: [`src/${layer}/**/*.{ts,tsx}`],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            ...above.map((upper) => ({
              group: [`@${upper}`, `@${upper}/*`],
              message: `Слой ${layer} не импортирует ${upper} (FSD: только вниз)`,
            })),
            // Чужой слайс — только через его index.ts (@features/auth, а не @features/auth/model/store).
            ...SLICE_LAYERS.map((slice) => ({
              group: [`@${slice}/*/*`],
              message: 'Импорт слайса только через его index.ts',
            })),
          ],
        },
      ],
    },
  };
};

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'src/shared/api/generated'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: { globals: globals.browser },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      curly: ['error', 'all'],
      'max-len': ['error', { code: 120, ignoreUrls: true, ignoreStrings: true }],
      '@typescript-eslint/consistent-type-imports': 'error',
      'no-restricted-syntax': [
        'error',
        { selector: 'JSXAttribute[name.name="dangerouslySetInnerHTML"]', message: 'Запрещено (XSS).' },
      ],
    },
  },
  ...LAYERS.map(layerRule),
);
