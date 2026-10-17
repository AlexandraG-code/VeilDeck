import { initReactI18next } from 'react-i18next';

import i18n from 'i18next';

import { Namespace } from './enums';
import enCatalog from './locales/catalog/en/catalog.json';
import ruCatalog from './locales/catalog/ru/catalog.json';
import enCommon from './locales/common/en/common.json';
import ruCommon from './locales/common/ru/common.json';
import enRequestAccess from './locales/requestAccess/en/requestAccess.json';
import ruRequestAccess from './locales/requestAccess/ru/requestAccess.json';

const DEFAULT_LANGUAGE = 'ru';

void i18n.use(initReactI18next).init({
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  defaultNS: Namespace.Common,
  ns: [Namespace.Common, Namespace.Catalog, Namespace.RequestAccess],
  resources: {
    ru: { [Namespace.Common]: ruCommon, [Namespace.Catalog]: ruCatalog, [Namespace.RequestAccess]: ruRequestAccess },
    en: { [Namespace.Common]: enCommon, [Namespace.Catalog]: enCatalog, [Namespace.RequestAccess]: enRequestAccess },
  },
  interpolation: { escapeValue: false },
});

export { Namespace } from './enums';
export { i18n };
