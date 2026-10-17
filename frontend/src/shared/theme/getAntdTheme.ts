import type { ThemeConfig } from 'antd';

const PRIMARY_COLOR = '#1f4e79';
const BORDER_RADIUS = 6;

/** Тема antd; цвета в компонентах берутся из токенов, а не хекс-литералами. */
export const getAntdTheme = (): ThemeConfig => ({
  token: { colorPrimary: PRIMARY_COLOR, borderRadius: BORDER_RADIUS },
});
