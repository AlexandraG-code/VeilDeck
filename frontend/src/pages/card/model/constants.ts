export const EMAIL_MAX_LENGTH = 254;
export const DISPLAY_NAME_MAX_LENGTH = 60;
export const PURPOSE_MAX_LENGTH = 1000;
export const PURPOSE_ROWS = 4;

/** Зеркало серверной проверки (SR-18): UI только подсказывает, решение принимает сервер. */
export const EMAIL_PATTERN =
  /^[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}$/;
export const DISPLAY_NAME_PATTERN = /^(?:[\p{L}\p{N}]|[ -])+$/u;
