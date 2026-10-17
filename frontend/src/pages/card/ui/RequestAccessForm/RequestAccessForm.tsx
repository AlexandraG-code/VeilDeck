import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Checkbox, Form, Input } from 'antd';

import { Namespace } from '@shared/i18n';

import {
  DISPLAY_NAME_MAX_LENGTH,
  DISPLAY_NAME_PATTERN,
  EMAIL_MAX_LENGTH,
  EMAIL_PATTERN,
  PURPOSE_MAX_LENGTH,
  PURPOSE_ROWS,
} from '../../model/constants';
import type { RequestAccessFormValues } from '../../model/types';
import { useRequestAccessForm } from '../../model/useRequestAccessForm';
import { RequestReceived } from '../RequestReceived';
import styles from './RequestAccessForm.module.scss';
import type { RequestAccessFormProps } from './types';

/** Форма запроса расширенного доступа; после отправки показывает экран «Запрос получен». */
export const RequestAccessForm: FC<RequestAccessFormProps> = ({ cardId }) => {
  const { t } = useTranslation(Namespace.RequestAccess);
  const { form, handleFinish, isPending, isReceived } = useRequestAccessForm(cardId);

  if (isReceived) {
    return <RequestReceived />;
  }

  return (
    <section aria-labelledby="request-access-title">
      <h2 id="request-access-title">{t('title')}</h2>
      <p className={styles.intro}>{t('intro')}</p>
      <Form<RequestAccessFormValues> form={form} layout="vertical" onFinish={handleFinish} requiredMark={false}>
        <Form.Item
          name="email"
          label={t('fields.email')}
          rules={[
            { required: true, message: t('validation.required') },
            { pattern: EMAIL_PATTERN, message: t('validation.email') },
          ]}
        >
          <Input type="email" autoComplete="email" maxLength={EMAIL_MAX_LENGTH} />
        </Form.Item>
        <Form.Item
          name="display_name"
          label={t('fields.displayName')}
          rules={[
            { required: true, whitespace: true, message: t('validation.required') },
            { pattern: DISPLAY_NAME_PATTERN, message: t('validation.displayName') },
          ]}
        >
          <Input autoComplete="nickname" maxLength={DISPLAY_NAME_MAX_LENGTH} />
        </Form.Item>
        <Form.Item
          name="purpose"
          label={t('fields.purpose')}
          rules={[{ required: true, whitespace: true, message: t('validation.required') }]}
        >
          <Input.TextArea rows={PURPOSE_ROWS} maxLength={PURPOSE_MAX_LENGTH} showCount />
        </Form.Item>
        {/* Honeypot: скрыт от людей и вспомогательных технологий, заполненный — признак бота */}
        <div className={styles.honeypot} aria-hidden="true">
          <Form.Item name="website" label="website">
            <Input tabIndex={-1} autoComplete="off" />
          </Form.Item>
        </div>
        <Form.Item
          name="consent"
          valuePropName="checked"
          rules={[
            {
              validator: (_, checked: boolean) =>
                checked ? Promise.resolve() : Promise.reject(new Error(t('validation.consent'))),
            },
          ]}
        >
          <Checkbox>{t('fields.consent')}</Checkbox>
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={isPending}>
          {t('submit')}
        </Button>
      </Form>
    </section>
  );
};
