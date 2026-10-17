import { Form } from 'antd';

import { useCreateAccessRequest } from '@shared/api/generated';

import type { RequestAccessFormValues } from './types';

/**
 * Состояние формы запроса доступа: отправка и признак «Запрос получен».
 * Ответ сервера одинаков для любого исхода (202), поэтому экран успеха не зависит от состояния карточки.
 * @param cardId идентификатор карточки из URL (на сервере проверяется ещё раз)
 */
export const useRequestAccessForm = (cardId: string) => {
  const [form] = Form.useForm<RequestAccessFormValues>();
  const { mutate, isPending, isSuccess } = useCreateAccessRequest();

  const handleFinish = (values: RequestAccessFormValues): void => {
    mutate({
      cardId,
      data: {
        email: values.email,
        display_name: values.display_name,
        purpose: values.purpose,
        consent: true,
        website: values.website ?? '',
      },
    });
  };

  return { form, handleFinish, isPending, isReceived: isSuccess };
};
