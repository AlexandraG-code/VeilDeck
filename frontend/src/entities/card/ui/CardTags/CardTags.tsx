import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

import { Tag } from 'antd';

import { Namespace } from '@shared/i18n';

import { enumLabelKey } from '../../lib/enumLabelKey';
import styles from './CardTags.module.scss';
import type { CardTagsProps } from './types';

/** Обобщённые признаки teaser-карточки (отрасль, регион, тип сделки, размер, выручка). */
export const CardTags: FC<CardTagsProps> = ({ card }) => {
  const { t } = useTranslation(Namespace.Catalog);

  return (
    <ul className={styles.list}>
      <li>
        <Tag>{t(enumLabelKey('industry', card.industry))}</Tag>
      </li>
      <li>
        <Tag>{t(enumLabelKey('region', card.region_macro))}</Tag>
      </li>
      <li>
        <Tag>{t(enumLabelKey('dealType', card.deal_type))}</Tag>
      </li>
      <li>
        <Tag>{t(enumLabelKey('size', card.size_band))}</Tag>
      </li>
      <li>
        <Tag>{t(enumLabelKey('revenue', card.revenue_band))}</Tag>
      </li>
    </ul>
  );
};
