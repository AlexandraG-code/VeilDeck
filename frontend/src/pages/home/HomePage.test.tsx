import { render, screen } from '@testing-library/react';

import { HomePage } from './HomePage';

describe('HomePage', () => {
  it('показывает заголовок', () => {
    render(<HomePage />);

    expect(screen.getByRole('heading', { name: 'VeilDeck' })).toBeInTheDocument();
  });
});
