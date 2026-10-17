import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Card } from 'antd';

import { Namespace } from '@shared/i18n';
import { formatDate } from '@shared/lib/format';

import { CardTags } from '../CardTags';
import styles from './CardTeaser.module.scss';
import type { CardTeaserProps } from './types';

/** Teaser-карточка: только обезличенные поля; текст выводится как текст, без HTML. */
export const CardTeaser: FC<CardTeaserProps> = ({ card, onOpen }) => {
  const { t, i18n } = useTranslation(Namespace.Catalog);

  const handleOpen = (): void => {
    onOpen?.(card.id);
  };

  return (
    <Card className={styles.card} title={card.title_generic}>
      <CardTags card={card} />
      <p className={styles.text}>{card.teaser_text}</p>
      {onOpen ? (
        <Button type="primary" onClick={handleOpen}>
          {t('open')}
        </Button>
      ) : null}
      <small className={styles.meta}>{t('published', { date: formatDate(card.published_at, i18n.language) })}</small>
    </Card>
  );
};
