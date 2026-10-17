import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { HOME_PATH } from '@shared/config';

import styles from './PageLayout.module.scss';
import type { PageLayoutProps } from './types';

/** Оболочка публичных страниц: шапка с названием продукта, заголовок и содержимое. */
export const PageLayout: FC<PageLayoutProps> = ({ title, subtitle, children }) => {
  const { t } = useTranslation();

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <Link className={styles.brand} to={HOME_PATH}>
          {t('appName')}
        </Link>
      </header>
      <main className={styles.content}>
        <h1 className={styles.title}>{title}</h1>
        {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
        {children}
      </main>
    </div>
  );
};
