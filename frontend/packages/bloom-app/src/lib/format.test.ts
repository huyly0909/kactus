import { describe, it, expect } from 'vitest';
import { fmt, fmtChange, fmtCompact, num, toneOf } from './format';

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

  it('maps a delta to the gain/loss token', () => {
    expect(toneOf('1')).toBe('text-[var(--gain)]');
    expect(toneOf('-1')).toBe('text-[var(--loss)]');
    expect(toneOf('0')).toBe('');
    expect(toneOf(null)).toBe('');
  });
});
