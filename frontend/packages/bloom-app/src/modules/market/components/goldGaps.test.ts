import { afterEach, describe, expect, it, vi } from 'vitest';
import type { GoldHistoryPoint, GoldScheduleResponse } from '@/types/market';
import { detectGaps, expectedDays, todayInTz, todayMissing, weekdayOf } from './goldGaps';

const pt = (date: string): GoldHistoryPoint => ({ code: 'X', date, unit: 'VND/luong' });

/** Mon–Fri, no holidays, interpreted in `tz`. */
const schedule = (
  tz: 'UTC' | 'Asia/Ho_Chi_Minh',
  holidays: string[] = [],
): GoldScheduleResponse => ({
  source: 'sjc',
  code: 'SJC',
  expected_weekdays: [0, 1, 2, 3, 4],
  holidays,
  timezone: tz,
  enabled: true,
});

afterEach(() => {
  vi.useRealTimers();
});

describe('weekdayOf', () => {
  it('maps to Python weekday (Mon=0 … Sun=6), timezone-neutral', () => {
    expect(weekdayOf('2024-01-01')).toBe(0); // Monday
    expect(weekdayOf('2024-01-05')).toBe(4); // Friday
    expect(weekdayOf('2024-01-06')).toBe(5); // Saturday
    expect(weekdayOf('2024-01-07')).toBe(6); // Sunday
  });
});

describe('expectedDays', () => {
  it('keeps weekdays, drops weekends', () => {
    expect(expectedDays('2024-01-01', '2024-01-07', schedule('UTC'))).toEqual([
      '2024-01-01',
      '2024-01-02',
      '2024-01-03',
      '2024-01-04',
      '2024-01-05',
    ]);
  });

  it('drops holidays', () => {
    expect(expectedDays('2024-01-01', '2024-01-05', schedule('UTC', ['2024-01-03']))).toEqual([
      '2024-01-01',
      '2024-01-02',
      '2024-01-04',
      '2024-01-05',
    ]);
  });
});

describe('detectGaps', () => {
  it('flags a real missing weekday, never a weekend', () => {
    const rows = ['2024-01-01', '2024-01-02', '2024-01-04', '2024-01-05'].map(pt); // 03 missing
    const gaps = detectGaps(rows, '2024-01-01', '2024-01-05', schedule('UTC'));
    expect(gaps).toEqual(['2024-01-03']);
  });

  it('does not flag a missing holiday', () => {
    const rows = ['2024-01-01', '2024-01-02', '2024-01-04', '2024-01-05'].map(pt); // 03 missing
    const gaps = detectGaps(rows, '2024-01-01', '2024-01-05', schedule('UTC', ['2024-01-03']));
    expect(gaps).toEqual([]);
  });

  it('clamps the lower bound to the earliest returned point (truncated response)', () => {
    // `from` empty (preset "all") but the backend cut the old end at 2024-01-02.
    const rows = ['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05'].map(pt);
    const gaps = detectGaps(rows, '', '2024-01-05', schedule('UTC'));
    expect(gaps).toEqual([]); // 2024-01-01 (a Monday) is before the data — not invented
  });

  it('clamps the upper bound to today and never counts today itself', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-05T10:00:00Z')); // today = Fri 2024-01-05 (UTC)
    const rows = ['2024-01-01', '2024-01-02', '2024-01-04'].map(pt); // 03 + 05 missing
    const gaps = detectGaps(rows, '2024-01-01', '', schedule('UTC'));
    expect(gaps).toEqual(['2024-01-03']); // 05 is today → owned by todayMissing, excluded
  });
});

describe('todayMissing', () => {
  it('is true when today is an expected day with no point', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-03T10:00:00Z')); // Wednesday
    expect(todayMissing([pt('2024-01-02')], schedule('UTC'))).toBe(true);
  });

  it('is false once today has a point', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-03T10:00:00Z'));
    expect(todayMissing([pt('2024-01-03')], schedule('UTC'))).toBe(false);
  });

  it('is false on a weekend or holiday', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-06T10:00:00Z')); // Saturday
    expect(todayMissing([], schedule('UTC'))).toBe(false);
    vi.setSystemTime(new Date('2024-01-03T10:00:00Z')); // Wednesday, but a holiday
    expect(todayMissing([], schedule('UTC', ['2024-01-03']))).toBe(false);
  });

  it('resolves "today" in the schedule timezone, not the browser', () => {
    // Fri 20:00 UTC is already Sat in ICT (UTC+7) → not an expected day there.
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-05T20:00:00Z'));
    expect(todayInTz('UTC')).toBe('2024-01-05'); // Friday
    expect(todayInTz('Asia/Ho_Chi_Minh')).toBe('2024-01-06'); // Saturday
    expect(todayMissing([], schedule('UTC'))).toBe(true); // Fri, expected, missing
    expect(todayMissing([], schedule('Asia/Ho_Chi_Minh'))).toBe(false); // Sat in ICT
  });
});
