import { DealType, Industry, RegionMacro } from '@shared/api/generated/model';

export const CATALOG_PAGE_SIZE = 12;

/** Значения фильтров каталога (enum из контракта API). */
export const INDUSTRY_VALUES = Object.values(Industry);
export const REGION_VALUES = Object.values(RegionMacro);
export const DEAL_TYPE_VALUES = Object.values(DealType);
