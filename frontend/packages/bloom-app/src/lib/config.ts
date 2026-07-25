export type SupportedLocale = 'vi' | 'en';

export const PLATFORM_CONFIG = {
  DEFAULT_LOCALE: 'vi' as SupportedLocale,
  SUPPORTED_LOCALES: ['vi', 'en'] as SupportedLocale[],
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL ?? '',
  DEV_PORT: 17630,
} as const;
