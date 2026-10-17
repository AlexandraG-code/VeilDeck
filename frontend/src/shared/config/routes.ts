/** Пути приложения: public (/, /cards/:cardId), viewer (/access, /viewer), staff (/staff/*). */
export const HOME_PATH = '/';
export const CARD_PATH = '/cards/:cardId';
export const ACCESS_PATH = '/access';
export const VIEWER_PATH = '/viewer';
export const STAFF_LOGIN_PATH = '/staff/login';
export const STAFF_HOME_PATH = '/staff';

/**
 * Путь страницы карточки по её публичному идентификатору (UUIDv4).
 * @param cardId идентификатор карточки
 */
export const getCardPath = (cardId: string): string => `/cards/${encodeURIComponent(cardId)}`;
