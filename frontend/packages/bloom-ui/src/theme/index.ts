import { type MantineThemeOverride } from '@mantine/core';

export const theme: MantineThemeOverride = {
    primaryColor: 'indigo',
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    headings: {
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    },
    defaultRadius: 'md',
    colors: {
        // Fintech-friendly custom color palette
        brand: [
            '#eef2ff',
            '#e0e7ff',
            '#c7d2fe',
            '#a5b4fc',
            '#818cf8',
            '#6366f1',
            '#4f46e5',
            '#4338ca',
            '#3730a3',
            '#312e81',
        ],
    },
    components: {
        Button: {
            defaultProps: {
                size: 'sm',
            },
        },
        TextInput: {
            defaultProps: {
                size: 'sm',
            },
        },
        Select: {
            defaultProps: {
                size: 'sm',
            },
        },
    },
};
