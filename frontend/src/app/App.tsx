import type { FC } from 'react';

import { QueryClientProvider } from '@tanstack/react-query';

import { ErrorNotifier } from './error-notification';
import { queryClient } from './queryClient';
import { AppRouter } from './routes/AppRouter';
import { ThemeProvider } from './theming';

/** Корень приложения: провайдеры, глобальный показ ошибок и роутер. */
export const App: FC = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <ErrorNotifier />
      <AppRouter />
    </ThemeProvider>
  </QueryClientProvider>
);
