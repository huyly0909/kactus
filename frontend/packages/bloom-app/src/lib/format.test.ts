import { describe, it, expect } from 'vitest';
import { fmt, fmtChange, fmtCompact, fmtGold, num, toneOf } from './format';

describe('format helpers', () => {
  it('parses API numeric strings', () => {
    expect(num('12.5')).toBe(12.5);
    expect(num('')).toBeNull();
    expect(num(null)).toBeNull();
    expect(num('abc')).toBeNull();
  });

  it('renders an em dash for missing values', () => {
    expect(fmt(null)).toBe('—');
    expect(fmtCompact(undefined)).toBe('—');
    expect(fmtChange(null)).toBe('—');
  });

  it('signs changes and appends the percentage', () => {
    expect(fmtChange('1.2', '2.4')).toBe('+1.20 (2.40%)');
    expect(fmtChange('-1.2', '-2.4')).toBe('-1.20 (-2.40%)');
    expect(fmtChange('1.2')).toBe('+1.20');
  });

  it('formats gold per its unit', () => {
    // Domestic gold is whole dong — cents would be noise on a 1.4e8 number.
    expect(fmtGold('135000000', 'VND/luong')).toBe('135,000,000');
    // World gold is ~4e3 USD, where cents are the whole point.
    expect(fmtGold('4037.6999', 'USD/oz')).toBe('4,037.70');
    // Unknown/absent unit falls back to the domestic (whole-number) shape.
    expect(fmtGold('135000000', null)).toBe('135,000,000');
    expect(fmtGold(null, 'USD/oz')).toBe('—');
  });

  it('does not let a USD/oz price masquerade as VND', () => {
    // The board mixes units, so the same value must render differently.
    expect(fmtGold('4037.6999', 'USD/oz')).not.toBe(fmtGold('4037.6999', 'VND/luong'));
  });

  it('maps a delta to the gain/loss token', () => {
    expect(toneOf('1')).toBe('text-[var(--gain)]');
    expect(toneOf('-1')).toBe('text-[var(--loss)]');
    expect(toneOf('0')).toBe('');
    expect(toneOf(null)).toBe('');
  });
});
