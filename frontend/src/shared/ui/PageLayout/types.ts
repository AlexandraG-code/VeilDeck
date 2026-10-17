import type { ReactNode } from 'react';

/** Параметры общей оболочки публичных страниц. */
export interface PageLayoutProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
}
