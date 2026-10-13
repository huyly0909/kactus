import { describe, expect, it } from 'vitest';
import { matchesSearch, normalizeText } from './text';

describe('normalizeText', () => {
  it('strips Vietnamese tone marks', () => {
    expect(normalizeText('Thành Đức')).toBe('thanh duc');
    expect(normalizeText('Hồng Cúc')).toBe('hong cuc');
    expect(normalizeText('Tiến Sơn')).toBe('tien son');
  });

  it('folds đ/Đ, which NFD leaves alone', () => {
    expect(normalizeText('Đường')).toBe('duong');
    expect(normalizeText('đỗ')).toBe('do');
  });

  it('lowercases and trims', () => {
    expect(normalizeText('  ALICE  ')).toBe('alice');
  });

  it('handles empty input', () => {
    expect(normalizeText('')).toBe('');
    expect(normalizeText(null)).toBe('');
    expect(normalizeText(undefined)).toBe('');
  });

  it('is idempotent', () => {
    const once = normalizeText('Nguyễn Đình Chiểu');
    expect(normalizeText(once)).toBe(once);
  });
});

describe('matchesSearch', () => {
  it('matches an accented name from an unaccented query', () => {
    expect(matchesSearch('Thành Đức', 'duc')).toBe(true);
    expect(matchesSearch('Tiến Sơn', 'SON')).toBe(true);
  });

  it('matches an unaccented name from an accented query', () => {
    expect(matchesSearch('Hong Cuc', 'Hồng')).toBe(true);
  });

  it('rejects a genuine non-match', () => {
    expect(matchesSearch('Thành Đức', 'alice')).toBe(false);
  });

  it('treats an empty query as "everything"', () => {
    expect(matchesSearch('anything', '')).toBe(true);
    expect(matchesSearch(null, '')).toBe(true);
  });
});
