import { describe, it, expect } from 'vitest';
import { escapeCSVCell, toCSV } from './csv';

describe('csv', () => {
  it('escapes commas, quotes and newlines; passes plain values through', () => {
    expect(escapeCSVCell('a,b')).toBe('"a,b"');
    expect(escapeCSVCell('a"b')).toBe('"a""b"');
    expect(escapeCSVCell('a\nb')).toBe('"a\nb"');
    expect(escapeCSVCell('plain')).toBe('plain');
    expect(escapeCSVCell(null)).toBe('');
    expect(escapeCSVCell(undefined)).toBe('');
    expect(escapeCSVCell(42)).toBe('42');
  });

  it('builds a header + body with CRLF separators and per-cell escaping', () => {
    const csv = toCSV(
      ['A', 'B'],
      [
        [1, 2],
        ['x,y', 'z'],
      ],
    );
    expect(csv).toBe('A,B\r\n1,2\r\n"x,y",z');
  });

  it('returns the header line alone when there are no rows', () => {
    expect(toCSV(['A', 'B'], [])).toBe('A,B');
  });
});
