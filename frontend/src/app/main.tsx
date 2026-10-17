import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import '@shared/i18n';

import { App } from './App';
import './styles/global.scss';

createRoot(document.getElementById('root') as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
