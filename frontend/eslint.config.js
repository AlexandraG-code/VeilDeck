import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'src/api/generated'] },
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
);
