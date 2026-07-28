/** Text normalisation helpers for client-side search. */

// đ/Đ is a distinct letter, not a base + combining mark, so NFD leaves it alone
// and stripping marks would never make "duc" match "Đức".
const D_STROKE = /[đĐÐ]/g;
const DIACRITICS = /\p{Diacritic}/gu;

/**
 * Fold a string to a diacritic-free, case-insensitive search key.
 *
 * Apply it to **both** sides of a comparison so a Vietnamese name matches what
 * the user types on an unaccented keyboard: `normalizeText('Thành Đức')` is
 * `'thanh duc'`, which `'duc'` is a substring of. Mirrors the backend's
 * `normalize_search` in `kactus_common/text.py` — keep the two in step.
 */
export function normalizeText(value: string | null | undefined): string {
  if (!value) return '';
  return value.replace(D_STROKE, 'd').normalize('NFD').replace(DIACRITICS, '').toLowerCase().trim();
}

/** Whether `haystack` contains `needle`, ignoring case and diacritics. */
export function matchesSearch(haystack: string | null | undefined, needle: string): boolean {
  const q = normalizeText(needle);
  return q === '' || normalizeText(haystack).includes(q);
}
