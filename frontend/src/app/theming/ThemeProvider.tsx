import type { FC, PropsWithChildren } from 'react';

import { ConfigProvider } from 'antd';

import { getAntdTheme } from '@shared/theme';

/** Применяет тему antd ко всему приложению. */
export const ThemeProvider: FC<PropsWithChildren> = ({ children }) => (
  <ConfigProvider theme={getAntdTheme()}>{children}</ConfigProvider>
);
