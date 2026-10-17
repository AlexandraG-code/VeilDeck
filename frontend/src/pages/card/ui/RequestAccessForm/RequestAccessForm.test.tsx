import { MemoryRouter } from 'react-router-dom';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { i18n } from '@shared/i18n';

import { RequestAccessForm } from './RequestAccessForm';

const mutate = vi.fn();
let isSuccess = false;

vi.mock('@shared/api/generated', () => ({
  useCreateAccessRequest: () => ({ mutate, isPending: false, isSuccess }),
}));

const CARD_ID = '5a2e0000-0000-4000-8000-000000000001';
const t = (key: string): string => i18n.t(key, { ns: 'requestAccess' });

const renderForm = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <RequestAccessForm cardId={CARD_ID} />
      </MemoryRouter>
    </QueryClientProvider>,
  );

describe('RequestAccessForm', () => {
  beforeEach(() => {
    mutate.mockReset();
    isSuccess = false;
  });

  it('не отправляет пустую форму и показывает ошибки', async () => {
    renderForm();

    await userEvent.click(screen.getByRole('button', { name: t('submit') }));

    expect(await screen.findByText(t('validation.consent'))).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });

  it('отклоняет некорректный e-mail и недопустимое имя', async () => {
    renderForm();

    await userEvent.type(screen.getByLabelText(t('fields.email')), 'not-an-email');
    await userEvent.type(screen.getByLabelText(t('fields.displayName')), '<b>Иван</b>');
    await userEvent.click(screen.getByRole('button', { name: t('submit') }));

    expect(await screen.findByText(t('validation.email'))).toBeInTheDocument();
    expect(screen.getByText(t('validation.displayName'))).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });

  it('отправляет только допустимые поля; карточка берётся из пропсов, honeypot пуст', async () => {
    renderForm();

    await userEvent.type(screen.getByLabelText(t('fields.email')), 'user@example.test');
    await userEvent.type(screen.getByLabelText(t('fields.displayName')), 'Иван Петров-Сидоров');
    await userEvent.type(screen.getByLabelText(t('fields.purpose')), 'Изучить партнёрство');
    await userEvent.click(screen.getByRole('checkbox', { name: t('fields.consent') }));
    await userEvent.click(screen.getByRole('button', { name: t('submit') }));

    await waitFor(() => expect(mutate).toHaveBeenCalledTimes(1));
    expect(mutate).toHaveBeenCalledWith({
      cardId: CARD_ID,
      data: {
        email: 'user@example.test',
        display_name: 'Иван Петров-Сидоров',
        purpose: 'Изучить партнёрство',
        consent: true,
        website: '',
      },
    });
  });

  it('honeypot скрыт от вспомогательных технологий и не доступен с клавиатуры', () => {
    renderForm();

    const honeypot = screen.getByLabelText('website', { selector: 'input' });

    expect(honeypot.closest('[aria-hidden="true"]')).not.toBeNull();
    expect(honeypot).toHaveAttribute('tabindex', '-1');
  });

  it('после успешной отправки показывает экран «Запрос получен»', () => {
    isSuccess = true;
    renderForm();

    expect(screen.getByText(t('received.title'))).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: t('submit') })).not.toBeInTheDocument();
  });
});
