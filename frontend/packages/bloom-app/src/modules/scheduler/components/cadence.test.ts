import { describe, expect, it } from 'vitest';
import en from '@/locales/en.json';
import vi from '@/locales/vi.json';
import { describeCadence, tzLabel } from './cadence';

const VN = 'Asia/Ho_Chi_Minh';

/** The six triggers `build_scheduler` actually registers. */
const REAL_CRONS = [
  { day_of_week: 'mon-fri', hour: '9-15', minute: '0' },
  { day_of_week: 'mon-fri', hour: '9-15', minute: '5' },
  { day_of_week: 'mon-fri', hour: '15', minute: '35' },
  { day_of_week: 'mon-fri', hour: '15', minute: '40' },
  { day_of_week: 'mon-fri', hour: '15', minute: '45' },
  { hour: '8', minute: '30' },
];

const lookup = (bundle: unknown, path: string): unknown =>
  path.split('.').reduce<unknown>((acc, k) => (acc as Record<string, unknown>)?.[k], bundle);

describe('describeCadence', () => {
  it('reads an hourly window as a range, keeping the offset minute', () => {
    // crawl_news: mon-fri, 09:00–15:00, at :05 past each hour.
    expect(describeCadence({ day_of_week: 'mon-fri', hour: '9-15', minute: '5' }, VN)).toEqual({
      key: 'scheduler.cadence.hourly_range_days',
      values: { days: 'mon-fri', from: '09:00', to: '15:00', minute: '05', tz: 'GMT+7' },
    });
  });

  it('reads a fixed time on set days', () => {
    expect(describeCadence({ day_of_week: 'mon-fri', hour: '15', minute: '35' }, VN)).toEqual({
      key: 'scheduler.cadence.daily_days',
      values: { days: 'mon-fri', at: '15:35', tz: 'GMT+7' },
    });
  });

  it('treats a missing day_of_week as every day — the weekend tell', () => {
    // sync_catalog is the only job with no day_of_week: it runs Sat/Sun too,
    // which the raw cron string hides.
    const out = describeCadence({ hour: '8', minute: '30' }, VN);
    expect(out?.key).toBe('scheduler.cadence.daily');
    expect(out?.values.days).toBeUndefined();
    expect(out?.values.at).toBe('08:30');
  });

  it('falls back to null for shapes it cannot phrase', () => {
    expect(describeCadence(null)).toBeNull();
    expect(describeCadence({ minute: '*/5' })).toBeNull();
    expect(describeCadence({ hour: '9-15', minute: '*/5' })).toBeNull();
  });

  it.each([
    ['en', en],
    ['vi', vi],
  ])('has a %s string for every trigger the scheduler registers', (_locale, bundle) => {
    // A missing key renders as the raw key in the table, silently — which is
    // exactly what this whole column was meant to stop showing.
    for (const cron of REAL_CRONS) {
      const parts = describeCadence(cron, VN);
      expect(parts, JSON.stringify(cron)).not.toBeNull();
      expect(lookup(bundle, parts!.key), parts!.key).toBeTypeOf('string');
      const dow = parts!.values.days;
      if (dow) expect(lookup(bundle, `scheduler.cadence.dow.${dow}`), dow).toBeTypeOf('string');
    }
  });

  it('omits the zone rather than guessing when it is unknown', () => {
    expect(tzLabel('Not/AZone')).toBeNull();
    expect(tzLabel(null)).toBeNull();
    expect(describeCadence({ hour: '8', minute: '30' })?.values.tz).toBe('');
  });
});
