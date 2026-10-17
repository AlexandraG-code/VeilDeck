import axios from 'axios';

import { CSRF_COOKIE, CSRF_URL, REQUEST_TIMEOUT_MS } from './constants';
import type { CsrfResponse } from './types';

/**
 * Читает значение cookie по имени.
 * @param name имя cookie
 */
export const readCookie = (name: string): string | undefined => {
  const prefix = `${name}=`;
  const entry = document.cookie.split('; ').find((part) => part.startsWith(prefix));

  return entry ? decodeURIComponent(entry.slice(prefix.length)) : undefined;
};

/**
 * Возвращает CSRF-токен: из cookie `__Host-csrf`, а если её ещё нет (до первого запроса), берёт у сервера.
 * Запрос идёт отдельным инстансом без перехватчиков, чтобы не зациклиться.
 */
export const ensureCsrfToken = async (): Promise<string> => {
  const fromCookie = readCookie(CSRF_COOKIE);

  if (fromCookie) {
    return fromCookie;
  }

  const response = await axios.get<CsrfResponse>(CSRF_URL, { timeout: REQUEST_TIMEOUT_MS, withCredentials: true });

  return response.data.csrf_token;
};
