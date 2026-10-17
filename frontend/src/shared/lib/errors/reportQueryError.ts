import { isAxiosError } from 'axios';

import { useErrorStore } from './store';

const UNAUTHORIZED = 401;
const FORBIDDEN = 403;
const TOO_MANY_REQUESTS = 429;
let nextId = 1;

/**
 * Приводит ошибку запроса к ключу i18n и кладёт в стор. 401 не показывается: на него реагируют guards.
 * @param error ошибка из QueryCache/MutationCache
 */
export const reportQueryError = (error: unknown): void => {
  const status = isAxiosError(error) ? error.response?.status : undefined;

  if (status === UNAUTHORIZED) {
    return;
  }

  const body = isAxiosError(error)
    ? (error.response?.data as { error?: { request_id?: string } } | undefined)
    : undefined;
  const messageKey =
    status === FORBIDDEN
      ? 'errors.forbidden'
      : status === TOO_MANY_REQUESTS
        ? 'errors.tooManyRequests'
        : 'errors.generic';

  useErrorStore.getState().report({ id: nextId++, messageKey, requestId: body?.error?.request_id });
};
