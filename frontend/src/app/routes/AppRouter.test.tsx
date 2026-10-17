import { RouterProvider, createMemoryRouter } from 'react-router-dom';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { i18n } from '@shared/i18n';

import { routes } from './AppRouter';
import { STAFF_HOME_PATH } from './constants';

vi.mock('@shared/api/generated', () => ({
  useStaffMe: () => ({ data: undefined, error: new Error('401'), isPending: false }),
}));

describe('зоны маршрутов', () => {
  it('без серверной сессии staff-зона ведёт на вход', async () => {
    const router = createMemoryRouter(routes, { initialEntries: [STAFF_HOME_PATH] });
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole('heading', { name: i18n.t('zones.staffLogin') })).toBeInTheDocument();
  });
});
