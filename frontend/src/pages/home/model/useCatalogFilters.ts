import { useSearchParams } from 'react-router-dom';

import { DEAL_TYPE_VALUES, INDUSTRY_VALUES, REGION_VALUES } from '@entities/card';

import type { CatalogFilters, FilterKey } from './types';

const FIRST_PAGE = 1;
const PAGE_PARAM = 'page';

/**
 * Читает значение фильтра из URL; неизвестные значения игнорируются (на сервере enum проверяется повторно).
 * @param raw значение параметра
 * @param allowed допустимые значения
 */
const pick = <T extends string>(raw: string | null, allowed: readonly T[]): T | undefined =>
  allowed.find((value) => value === raw);

/** Фильтры и страница каталога в строке запроса. */
export const useCatalogFilters = () => {
  const [params, setParams] = useSearchParams();

  const filters: CatalogFilters = {
    industry: pick(params.get('industry'), INDUSTRY_VALUES),
    region_macro: pick(params.get('region_macro'), REGION_VALUES),
    deal_type: pick(params.get('deal_type'), DEAL_TYPE_VALUES),
  };
  const parsedPage = Number(params.get(PAGE_PARAM));
  const page = Number.isInteger(parsedPage) && parsedPage >= FIRST_PAGE ? parsedPage : FIRST_PAGE;

  const setFilter = (key: FilterKey, value?: string): void => {
    const next = new URLSearchParams(params);

    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    next.delete(PAGE_PARAM);
    setParams(next);
  };

  const setPage = (nextPage: number): void => {
    const next = new URLSearchParams(params);

    next.set(PAGE_PARAM, String(nextPage));
    setParams(next);
  };

  const resetFilters = (): void => {
    setParams(new URLSearchParams());
  };

  return { filters, page, setFilter, setPage, resetFilters };
};
