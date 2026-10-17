/**
 * Форматирует ISO-дату по локали интерфейса (только дата, без времени).
 * @param iso дата в формате ISO 8601
 * @param locale код языка, например "ru"
 */
export const formatDate = (iso: string, locale: string): string =>
  new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(new Date(iso));
