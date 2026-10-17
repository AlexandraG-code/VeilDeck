import axios, { type AxiosRequestConfig } from 'axios';

import { CSRF_HEADER, REQUEST_TIMEOUT_MS, STATE_CHANGING_METHODS } from './constants';
import { ensureCsrfToken } from './csrf';

/** Единый axios-инстанс: same-origin, cookie-сессия, CSRF-заголовок на изменяющих методах. */
export const axiosInstance = axios.create({ baseURL: '/', timeout: REQUEST_TIMEOUT_MS, withCredentials: true });

axiosInstance.interceptors.request.use(async (config) => {
  if (STATE_CHANGING_METHODS.includes((config.method ?? 'get').toLowerCase())) {
    config.headers.set(CSRF_HEADER, await ensureCsrfToken());
  }

  return config;
});

/**
 * Mutator для orval: выполняет запрос и возвращает только данные.
 * @param config конфигурация запроса, собранная сгенерированным клиентом
 * @param options дополнительные опции запроса от хука
 */
export const apiClient = async <T>(config: AxiosRequestConfig, options?: AxiosRequestConfig): Promise<T> => {
  const response = await axiosInstance.request<T>({ ...config, ...options });

  return response.data;
};
