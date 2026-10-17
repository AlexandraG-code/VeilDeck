import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';

import { Alert, Spin } from 'antd';

import { CardTeaser, useTeaserCard } from '@entities/card';
import { NOT_FOUND_STATUS, getApiErrorStatus } from '@shared/api';
import { HOME_PATH } from '@shared/config';
import { Namespace } from '@shared/i18n';
import { PageLayout } from '@shared/ui';

import styles from './CardPage.module.scss';
import { RequestAccessForm } from './RequestAccessForm';

/** Страница опубликованной teaser-карточки и форма запроса расширенного доступа. */
export const CardPage: FC = () => {
  const { t } = useTranslation(Namespace.Catalog);
  const { cardId = '' } = useParams();
  const { data, error, isPending } = useTeaserCard(cardId);

  if (isPending) {
    return (
      <PageLayout title={t('title')}>
        <Spin />
      </PageLayout>
    );
  }

  if (!data) {
    // 404 (черновик, архив, несуществующая) неразличимы; прочие сбои — отдельное сообщение, детали у ErrorNotifier
    const isNotFound = getApiErrorStatus(error) === NOT_FOUND_STATUS;

    return (
      <PageLayout title={t('title')}>
        <Alert type={isNotFound ? 'warning' : 'error'} message={isNotFound ? t('notFound') : t('loadFailed')} />
        <p>
          <Link to={HOME_PATH}>{t('back')}</Link>
        </p>
      </PageLayout>
    );
  }

  return (
    <PageLayout title={data.title_generic}>
      <CardTeaser card={data} />
      <div className={styles.section}>
        <RequestAccessForm cardId={cardId} />
      </div>
      <p>
        <Link to={HOME_PATH}>{t('back')}</Link>
      </p>
    </PageLayout>
  );
};
