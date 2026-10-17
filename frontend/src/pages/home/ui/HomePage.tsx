import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

/** Заглушка главной страницы; каталог teaser'ов добавляется в задаче 5.3. */
export const HomePage: FC = () => {
  const { t } = useTranslation();

  return <h1>{t('appName')}</h1>;
};
