import { MemoryRouter } from 'react-router-dom';

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { i18n } from '@shared/i18n';

import { CatalogBrowser } from './CatalogBrowser';

const useListCatalogCards = vi.fn();

vi.mock('@shared/api/generated', async () => ({
  ...(await vi.importActual<Record<string, unknown>>('@shared/api/generated')),
  useListCatalogCards: (params: unknown) => useListCatalogCards(params),
}));

const CARD = {
  id: '5a2e0000-0000-4000-8000-000000000001',
  title_generic: 'Производитель компонентов',
  industry: 'manufacturing',
  region_macro: 'europe',
  size_band: '50_to_249',
  revenue_band: '10m_to_50m',
  deal_type: 'equity',
  teaser_text: '<script>alert(1)</script> Региональный производитель',
  published_at: '2026-10-01T00:00:00Z',
};
const t = (key: string): string => i18n.t(key, { ns: 'catalog' });

const renderBrowser = (initialEntry = '/') =>
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <CatalogBrowser />
    </MemoryRouter>,
  );

describe('CatalogBrowser', () => {
  beforeEach(() => {
    useListCatalogCards.mockReset();
    useListCatalogCards.mockReturnValue({
      data: { items: [CARD], page: 1, page_size: 12, total: 1 },
      isPending: false,
      isError: false,
    });
  });

  it('показывает teaser-карточки и выводит текст как текст, без HTML', () => {
    renderBrowser();

    expect(screen.getByText('Производитель компонентов')).toBeInTheDocument();
    expect(screen.getByText(/<script>alert\(1\)<\/script>/)).toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
    expect(screen.getByText(t('enums.industry.manufacturing'))).toBeInTheDocument();
  });

  it('читает фильтры из URL и игнорирует неизвестные значения', () => {
    renderBrowser('/?industry=logistics&region_macro=bogus&page=2');

    expect(useListCatalogCards).toHaveBeenLastCalledWith({
      industry: 'logistics',
      region_macro: undefined,
      deal_type: undefined,
      page: 2,
      page_size: 12,
    });
  });

  it('при пустой выдаче показывает сообщение', () => {
    useListCatalogCards.mockReturnValue({
      data: { items: [], page: 1, page_size: 12, total: 0 },
      isPending: false,
      isError: false,
    });
    renderBrowser();

    expect(screen.getByText(t('empty'))).toBeInTheDocument();
  });

  it('сброс фильтров возвращает запрос без параметров', async () => {
    renderBrowser('/?industry=logistics');

    await userEvent.click(screen.getByRole('button', { name: t('filters.reset') }));

    expect(useListCatalogCards).toHaveBeenLastCalledWith({
      industry: undefined,
      region_macro: undefined,
      deal_type: undefined,
      page: 1,
      page_size: 12,
    });
  });
});
