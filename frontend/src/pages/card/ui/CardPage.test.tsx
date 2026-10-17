import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { i18n } from '@shared/i18n';

import { CardPage } from './CardPage';

const useGetCatalogCard = vi.fn();

vi.mock('@shared/api/generated', async () => ({
  ...(await vi.importActual<Record<string, unknown>>('@shared/api/generated')),
  useGetCatalogCard: (id: string) => useGetCatalogCard(id),
  useCreateAccessRequest: () => ({ mutate: vi.fn(), isPending: false, isSuccess: false }),
}));

const ID = '5a2e0000-0000-4000-8000-000000000001';
const t = (key: string, ns = 'catalog'): string => i18n.t(key, { ns });

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={[`/cards/${ID}`]}>
      <Routes>
        <Route path="/cards/:cardId" element={<CardPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe('CardPage', () => {
  beforeEach(() => useGetCatalogCard.mockReset());

  it('для опубликованной карточки показывает teaser и форму запроса', () => {
    useGetCatalogCard.mockReturnValue({
      data: {
        id: ID,
        title_generic: 'Производитель компонентов',
        industry: 'manufacturing',
        region_macro: 'europe',
        size_band: '50_to_249',
        revenue_band: '10m_to_50m',
        deal_type: 'equity',
        teaser_text: 'Описание',
        published_at: '2026-10-01T00:00:00Z',
      },
      isPending: false,
    });
    renderPage();

    expect(useGetCatalogCard).toHaveBeenCalledWith(ID);
    expect(screen.getByRole('heading', { name: 'Производитель компонентов' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: t('title', 'requestAccess') })).toBeInTheDocument();
  });

  it('для 404 показывает «не найдена» без формы (черновик и несуществующая неразличимы)', () => {
    useGetCatalogCard.mockReturnValue({
      data: undefined,
      error: { isAxiosError: true, response: { status: 404 } },
      isPending: false,
    });
    renderPage();

    expect(screen.getByText(t('notFound'))).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: t('submit', 'requestAccess') })).not.toBeInTheDocument();
  });

  it('для 500 показывает сообщение о сбое загрузки, а не «не найдена»', () => {
    useGetCatalogCard.mockReturnValue({
      data: undefined,
      error: { isAxiosError: true, response: { status: 500 } },
      isPending: false,
    });
    renderPage();

    expect(screen.getByText(t('loadFailed'))).toBeInTheDocument();
    expect(screen.queryByText(t('notFound'))).not.toBeInTheDocument();
  });
});
