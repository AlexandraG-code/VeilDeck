import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

import { Namespace } from '@shared/i18n';
import { PageLayout } from '@shared/ui';

import { CatalogBrowser } from './CatalogBrowser';

/** Главная: публичный каталог teaser-карточек. */
export const HomePage: FC = () => {
  const { t } = useTranslation(Namespace.Catalog);

  return (
    <PageLayout title={t('title')} subtitle={t('subtitle')}>
      <CatalogBrowser />
    </PageLayout>
  );
};
