import type { DealType, Industry, RegionMacro } from '@shared/api/generated/model';

/** Фильтры каталога, хранимые в строке запроса (ссылкой можно поделиться). */
export interface CatalogFilters {
  industry?: Industry;
  region_macro?: RegionMacro;
  deal_type?: DealType;
}

export type FilterKey = keyof CatalogFilters;
