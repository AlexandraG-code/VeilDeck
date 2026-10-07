import type { FC } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { AppRouter } from './routes/AppRouter';

const queryClient = new QueryClient();

/** Корень приложения: провайдеры и роутер. */
export const App: FC = () => (
  <QueryClientProvider client={queryClient}>
    <AppRouter />
  </QueryClientProvider>
);
