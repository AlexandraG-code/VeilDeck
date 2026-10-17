import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { Alert, Button, Empty, Pagination, Select, Spin } from 'antd';

import type { EnumGroup } from '@entities/card';
import {
  CATALOG_PAGE_SIZE,
  CardTeaser,
  DEAL_TYPE_VALUES,
  INDUSTRY_VALUES,
  REGION_VALUES,
  enumLabelKey,
  useCatalogPage,
} from '@entities/card';
import { getCardPath } from '@shared/config';
import { Namespace } from '@shared/i18n';

import { useCatalogFilters } from '../../model/useCatalogFilters';
import styles from './CatalogBrowser.module.scss';

/** Каталог teaser-карточек: фильтры по обобщённым признакам, список и постраничная выдача. */
export const CatalogBrowser: FC = () => {
  const { t } = useTranslation(Namespace.Catalog);
  const navigate = useNavigate();
  const { filters, page, setFilter, setPage, resetFilters } = useCatalogFilters();
  const { data, isPending, isError } = useCatalogPage({ ...filters, page, page_size: CATALOG_PAGE_SIZE });

  const toOptions = (group: EnumGroup, values: readonly string[]) =>
    values.map((value) => ({ value, label: t(enumLabelKey(group, value)) }));

  const handleOpen = (cardId: string): void => {
    void navigate(getCardPath(cardId));
  };

  return (
    <div>
      <div className={styles.filters}>
        <Select
          className={styles.filter}
          allowClear
          placeholder={t('filters.industry')}
          aria-label={t('filters.industry')}
          value={filters.industry}
          options={toOptions('industry', INDUSTRY_VALUES)}
          onChange={(value) => setFilter('industry', value)}
        />
        <Select
          className={styles.filter}
          allowClear
          placeholder={t('filters.region')}
          aria-label={t('filters.region')}
          value={filters.region_macro}
          options={toOptions('region', REGION_VALUES)}
          onChange={(value) => setFilter('region_macro', value)}
        />
        <Select
          className={styles.filter}
          allowClear
          placeholder={t('filters.dealType')}
          aria-label={t('filters.dealType')}
          value={filters.deal_type}
          options={toOptions('dealType', DEAL_TYPE_VALUES)}
          onChange={(value) => setFilter('deal_type', value)}
        />
        <Button onClick={resetFilters}>{t('filters.reset')}</Button>
      </div>
      {isPending ? <Spin /> : null}
      {isError ? <Alert type="error" message={t('loadFailed')} /> : null}
      {data && data.items.length === 0 ? <Empty description={t('empty')} /> : null}
      {data && data.items.length > 0 ? (
        <>
          <ul className={styles.grid}>
            {data.items.map((card) => (
              <li key={card.id}>
                <CardTeaser card={card} onOpen={handleOpen} />
              </li>
            ))}
          </ul>
          <div className={styles.pagination}>
            <Pagination
              current={data.page}
              pageSize={data.page_size}
              total={data.total}
              showSizeChanger={false}
              hideOnSinglePage
              onChange={setPage}
            />
          </div>
        </>
      ) : null}
    </div>
  );
};
