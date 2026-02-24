/**
 * Format a number as currency.
 * @example formatCurrency(1234.5) → "$1,234.50"
 */
export const formatCurrency = (
    value: number,
    currency = 'USD',
    locale = 'en-US',
): string => {
    return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(value);
};

/**
 * Format a number with thousand separators.
 * @example formatNumber(1234567) → "1,234,567"
 */
export const formatNumber = (value: number, locale = 'en-US'): string => {
    return new Intl.NumberFormat(locale).format(value);
};

/**
 * Format a number as percentage.
 * @example formatPercent(0.1234) → "12.34%"
 */
export const formatPercent = (
    value: number,
    decimals = 2,
    locale = 'en-US',
): string => {
    return new Intl.NumberFormat(locale, {
        style: 'percent',
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(value);
};

/**
 * Format a date string or Date object.
 * @example formatDate('2024-01-15') → "Jan 15, 2024"
 */
export const formatDate = (
    date: string | Date,
    locale = 'en-US',
    options?: Intl.DateTimeFormatOptions,
): string => {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleDateString(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        ...options,
    });
};

/**
 * Format a date string or Date object with time.
 * @example formatDateTime('2024-01-15T10:30:00') → "Jan 15, 2024, 10:30 AM"
 */
export const formatDateTime = (
    date: string | Date,
    locale = 'en-US',
): string => {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleString(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    });
};
