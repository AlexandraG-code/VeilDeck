/** Имя заголовка CSRF и cookie double-submit (контракт backend/app/api/csrf.py, SR-05). */
export const CSRF_HEADER = 'X-CSRF-Token';
export const CSRF_COOKIE = '__Host-csrf';
export const CSRF_URL = '/api/v1/csrf';

/** Методы, для которых backend требует CSRF-токен. */
export const STATE_CHANGING_METHODS = ['post', 'put', 'patch', 'delete'];

export const REQUEST_TIMEOUT_MS = 15000;
