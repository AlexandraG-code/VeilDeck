import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

/** Заглушка зоны «viewer»; содержимое добавляется в задаче 7.7. */
export const ViewerPage: FC = () => {
  const { t } = useTranslation();

  return <h1>{t('zones.viewer')}</h1>;
};
