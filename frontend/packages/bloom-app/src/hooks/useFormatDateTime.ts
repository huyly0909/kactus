import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { formatDate, formatDateTime } from '@/lib/locale-format';
import { useAuthStore } from '@/store/authStore';
import { DEFAULT_TIMEZONE } from '@/hooks/usePreferences';

function useLocaleTz(): { locale: string; tz: string } {
  const { i18n } = useTranslation();
  const tz = useAuthStore((s) => s.user?.timezone) || DEFAULT_TIMEZONE;
  const locale = i18n.language?.startsWith('en') ? 'en-US' : 'vi-VN';
  return { locale, tz };
}

/**
 * Returns a formatter that renders an API timestamp in the user's chosen
 * timezone and locale.
 *
 * API timestamps arrive as UTC ISO strings (with a `+00:00` offset — the
 * OLAP `event_dt` / `crawled_at` / `synced_at` columns). Displaying them
 * through this hook converts them to `user.timezone` (default
 * `Asia/Ho_Chi_Minh`), so picking UTC+7 shows correct Vietnam wall-clock.
 * Reactive: re-renders when the user changes their timezone/language.
 */
export function useFormatDateTime(): (value?: string | null) => string {
  const { locale, tz } = useLocaleTz();

  return useCallback(
    (value?: string | null) => {
      if (!value) return '—';
      const d = new Date(value);
      return Number.isNaN(d.getTime()) ? value : formatDateTime(d, locale, tz);
    },
    [locale, tz],
  );
}

/**
 * Date-only counterpart of {@link useFormatDateTime}.
 *
 * Converts a UTC `event_dt` to the user's timezone first, then drops the time —
 * so a daily bar stored as the previous day's 17:00 UTC still renders on its
 * correct Vietnam trading day when the user views in UTC+7.
 */
export function useFormatDate(): (value?: string | null) => string {
  const { locale, tz } = useLocaleTz();

  return useCallback(
    (value?: string | null) => {
      if (!value) return '—';
      const d = new Date(value);
      return Number.isNaN(d.getTime()) ? value : formatDate(d, locale, tz);
    },
    [locale, tz],
  );
}
