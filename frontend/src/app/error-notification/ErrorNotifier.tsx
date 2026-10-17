import { type FC, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import { notification } from 'antd';

import { useErrorStore } from '@shared/lib/errors';

/** Единственное место, где ошибки запросов показываются пользователю (текст без стек-трейса, с request_id). */
export const ErrorNotifier: FC = () => {
  const lastError = useErrorStore((state) => state.lastError);
  const clear = useErrorStore((state) => state.clear);
  const { t } = useTranslation();
  const [api, holder] = notification.useNotification();

  const showError = useCallback((): void => {
    if (!lastError) {
      return;
    }

    api.error({
      key: String(lastError.id),
      message: t(lastError.messageKey),
      description: lastError.requestId ? t('errors.requestId', { id: lastError.requestId }) : undefined,
    });
    clear();
  }, [api, clear, lastError, t]);

  useEffect(() => {
    showError();
  }, [showError]);

  return holder;
};
