import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

/** Заглушка зоны «staffHome»; содержимое добавляется в задаче 4.5. */
export const StaffHomePage: FC = () => {
  const { t } = useTranslation();

  return <h1>{t('zones.staffHome')}</h1>;
};
