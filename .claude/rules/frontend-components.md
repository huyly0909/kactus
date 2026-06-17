---
description: Component development patterns for usonia-ui
globs: ["frontend/**/components/**"]
---

# Component Development

## Structure
Each component lives in a PascalCase folder with:
- `MyComponent.tsx` — Component implementation
- `index.ts` — Re-export barrel
- `MyComponent.test.tsx` — Tests (optional)

## Pattern
```typescript
import { type FC } from 'react';
import { Card, Text } from '@mantine/core';
import { Activity } from 'lucide-react';

interface MyComponentProps {
  title: string;
  value: number;
}

export const MyComponent: FC<MyComponentProps> = ({ title, value }) => {
  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Text fw={600}>{title}: {value}</Text>
    </Card>
  );
};
```

## Available Shared Components
- `AppLayout` — Application shell with sidebar + header
- `ChartCard` — Card with embedded Recharts (line/bar/area)
- `DataTable` — Searchable, paginated table
- `StatCard` — KPI metric card (icon + value + title)
- `StatusBadge` — Color-coded status badge
- `LogViewer` — Filterable log viewer with pagination
