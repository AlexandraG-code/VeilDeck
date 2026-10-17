import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';

import { reportQueryError } from '@shared/lib/errors';

/** Клиент TanStack Query с глобальной обработкой ошибок: показывает их только ErrorNotifier. */
export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: reportQueryError }),
  mutationCache: new MutationCache({ onError: reportQueryError }),
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});
