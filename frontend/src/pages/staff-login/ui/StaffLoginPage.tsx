import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

/** Заглушка зоны «staffLogin»; содержимое добавляется в задаче 3.4. */
export const StaffLoginPage: FC = () => {
  const { t } = useTranslation();

  return <h1>{t('zones.staffLogin')}</h1>;
};
