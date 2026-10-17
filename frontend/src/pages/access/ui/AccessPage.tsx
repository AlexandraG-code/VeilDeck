import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

/** Заглушка зоны «access»; содержимое добавляется в задаче 7.6. */
export const AccessPage: FC = () => {
  const { t } = useTranslation();

  return <h1>{t('zones.access')}</h1>;
};
