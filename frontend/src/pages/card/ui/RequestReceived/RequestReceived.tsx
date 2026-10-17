import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Button, Result } from 'antd';

import { HOME_PATH } from '@shared/config';
import { Namespace } from '@shared/i18n';

/** Экран «Запрос получен»: одинаков для нового запроса, дубля и любого другого исхода. */
export const RequestReceived: FC = () => {
  const { t } = useTranslation(Namespace.RequestAccess);

  return (
    <Result
      status="success"
      title={t('received.title')}
      subTitle={t('received.subtitle')}
      extra={
        <Link to={HOME_PATH}>
          <Button type="primary">{t('received.back')}</Button>
        </Link>
      }
    />
  );
};
