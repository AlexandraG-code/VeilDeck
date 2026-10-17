import { initReactI18next } from 'react-i18next';

import i18n from 'i18next';

import { Namespace } from './enums';
import enCommon from './locales/common/en/common.json';
import ruCommon from './locales/common/ru/common.json';

const DEFAULT_LANGUAGE = 'ru';

void i18n.use(initReactI18next).init({
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  defaultNS: Namespace.Common,
  ns: [Namespace.Common],
  resources: {
    ru: { [Namespace.Common]: ruCommon },
    en: { [Namespace.Common]: enCommon },
  },
  interpolation: { escapeValue: false },
});

export { Namespace } from './enums';
export { i18n };
