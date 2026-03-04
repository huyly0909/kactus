---
name: component-development
description: Use when creating or modifying React components, forms, or UI elements. Covers component patterns, Mantine usage, React Hook Form + Zod, and notifications.
---

# Component Development Skill

## Component Folder Pattern

Each shared component lives in its own folder with a named export barrel:

```
bloom-ui/src/components/
├── DataTable/
│   ├── DataTable.tsx    # Component implementation
│   └── index.ts         # export { DataTable } from './DataTable';
├── ChartCard/
│   ├── ChartCard.tsx
│   └── index.ts
└── index.ts             # Barrel: re-exports all components
```

After creating a component folder, add it to `components/index.ts`:
```tsx
export { DataTable } from './DataTable';
export { MyComponent } from './MyComponent';  // ← add
```

## Component Pattern

Always use named exports, `FC`, and typed props:

```tsx
import { type FC } from 'react';
import { Card, Text, Group, Loader, Center } from '@mantine/core';

interface UserCardProps {
  name: string;
  balance: number;
  loading?: boolean;
}

export const UserCard: FC<UserCardProps> = ({ name, balance, loading = false }) => {
  if (loading) {
    return (
      <Center py="xl">
        <Loader size="lg" />
      </Center>
    );
  }

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Text fw={500}>{name}</Text>
      <Text size="xl">${balance.toLocaleString()}</Text>
    </Card>
  );
};
```

## Rules

- **Named exports** only — no `export default`
- **Typed props** via `interface` — never skip prop types
- **Functional components** only — no class components
- **Mantine** for all UI primitives — never Ant Design, MUI, or Chakra
- **Lucide React** for icons
- **Loading states** — use `<Loader />` from Mantine with `<Center>`

## Where Components Go

| Component type | Location | Import from |
|---------------|----------|-------------|
| Shared / reusable | `bloom-ui/src/components/<Name>/` | `@kactus-bloom/ui` |
| Page-specific | `bloom-app/src/pages/<PageName>/` | local import |

## Generic Components (existing)

| Component | Purpose |
|-----------|---------|
| `AppLayout` | Sidebar + header shell (used by MainLayout, AdminLayout) |
| `DataTable` | Rich table with search, pagination, custom column rendering |
| `ChartCard` | Recharts wrapper card |
| `ChatBox` | WebSocket-powered chat widget |

## Forms with React Hook Form + Zod

```tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { TextInput, Button } from '@mantine/core';

const schema = z.object({
  email: z.string().email(),
  amount: z.number().positive(),
});

type FormData = z.infer<typeof schema>;

export const TransferForm: FC = () => {
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = (data: FormData) => {
    // use useApiMutation here
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <TextInput label="Email" error={errors.email?.message} {...register('email')} />
      <Button type="submit">Submit</Button>
    </form>
  );
};
```

## Notifications

```tsx
// In-app toast (Mantine)
import { notifications } from '@mantine/notifications';

notifications.show({
  title: 'Saved',
  message: 'Record updated successfully',
  color: 'green',
});

// Browser push notification (custom hook)
import { useNotification } from '@kactus-bloom/ui/hooks';

const { sendBrowserNotification } = useNotification();
sendBrowserNotification('New Alert', 'Your report is ready.');
```

## Checklist

1. [ ] Component lives in `<Name>/` folder with `<Name>.tsx` + `index.ts`
2. [ ] Uses named export (no `export default`)
3. [ ] Props defined via `interface`
4. [ ] Uses `FC<Props>` typing
5. [ ] Uses Mantine components for UI primitives
6. [ ] Loading states handled with `<Loader />`
7. [ ] Added to `components/index.ts` barrel
8. [ ] Forms use React Hook Form + Zod
9. [ ] Tests written (see `testing.md`)
