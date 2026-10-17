import axios from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { axiosInstance } from './client';
import { CSRF_COOKIE, CSRF_HEADER } from './constants';
import { ensureCsrfToken, readCookie } from './csrf';

const TOKEN = 'token-from-cookie';

/** Префикс __Host- требует Secure/HTTPS, которого нет в happy-dom, поэтому подменяем чтение cookie. */
const setCookie = (value: string): void => {
  vi.spyOn(document, 'cookie', 'get').mockReturnValue(value);
};

describe('CSRF', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('берёт токен из cookie без запроса к серверу', async () => {
    setCookie(`${CSRF_COOKIE}=${TOKEN}`);
    const get = vi.spyOn(axios, 'get');

    expect(readCookie(CSRF_COOKIE)).toBe(TOKEN);
    expect(await ensureCsrfToken()).toBe(TOKEN);
    expect(get).not.toHaveBeenCalled();
  });

  it('без cookie запрашивает токен у сервера', async () => {
    setCookie('');
    vi.spyOn(axios, 'get').mockResolvedValue({ data: { csrf_token: 'from-server' } });

    expect(await ensureCsrfToken()).toBe('from-server');
  });

  it('добавляет заголовок на POST и не добавляет на GET', async () => {
    setCookie(`${CSRF_COOKIE}=${TOKEN}`);
    const sent: Record<string, unknown>[] = [];
    axiosInstance.defaults.adapter = async (config) => {
      sent.push({ method: config.method, header: config.headers.get(CSRF_HEADER) });

      return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
    };

    await axiosInstance.post('/api/v1/x', {});
    await axiosInstance.get('/api/v1/x');

    expect(sent).toEqual([
      { method: 'post', header: TOKEN },
      { method: 'get', header: undefined },
    ]);
  });
});
