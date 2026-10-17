import { MemoryRouter } from 'react-router-dom';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { i18n } from '@shared/i18n';

import { HomePage } from './HomePage';

vi.mock('@shared/api/generated', async () => ({
  ...(await vi.importActual<Record<string, unknown>>('@shared/api/generated')),
  useListCatalogCards: () => ({
    data: { items: [], page: 1, page_size: 12, total: 0 },
    isPending: false,
    isError: false,
  }),
}));

describe('HomePage', () => {
  it('показывает заголовок каталога', () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByRole('heading', { name: i18n.t('catalog:title') })).toBeInTheDocument();
  });
});
