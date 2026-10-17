import { isAxiosError } from 'axios';

export const UNAUTHORIZED_STATUS = 401;
export const NOT_FOUND_STATUS = 404;

/**
 * Возвращает HTTP-статус ошибки запроса или undefined, если это не ответ сервера.
 * @param error ошибка из TanStack Query
 */
export const getApiErrorStatus = (error: unknown): number | undefined =>
  isAxiosError(error) ? error.response?.status : undefined;
