import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import vi from './locales/vi.json';
import en from './locales/en.json';

void i18n.use(initReactI18next).init({
  resources: {
    vi: { translation: vi },
    en: { translation: en },
  },
  // English is the source language: every string is authored in en.json and
  // translated from there. A signed-in user's saved preference overrides this
  // via `applyUserLanguage` on session start.
  lng: 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
  keySeparator: '.',
  nsSeparator: false,
});

export async function setLanguage(lang: string): Promise<void> {
  await i18n.changeLanguage(lang);
}

export default i18n;
