import axios, { type AxiosRequestConfig } from 'axios';

const REQUEST_TIMEOUT_MS = 15000;

/** Единый axios-инстанс: same-origin, cookie-сессия; CSRF-заголовок добавляется в задаче 3.4. */
export const axiosInstance = axios.create({ baseURL: '/', timeout: REQUEST_TIMEOUT_MS, withCredentials: true });

/**
 * Mutator для orval: выполняет запрос и возвращает только данные.
 * @param config конфигурация запроса, собранная сгенерированным клиентом
 */
export const apiClient = async <T>(config: AxiosRequestConfig): Promise<T> => {
  const response = await axiosInstance.request<T>(config);

  return response.data;
};
