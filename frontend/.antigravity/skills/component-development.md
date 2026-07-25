---
name: component-development
description: Use when creating or modifying React components, forms, or UI elements. Covers component patterns, shadcn/ui usage, React Hook Form + Zod, and notifications.
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
import { Loader2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface UserCardProps {
  name: string;
  balance: number;
  loading?: boolean;
}

export const UserCard: FC<UserCardProps> = ({ name, balance, loading = false }) => {
  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-medium">{name}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xl">${balance.toLocaleString()}</p>
      </CardContent>
    </Card>
  );
};
```

## Rules

- **Named exports** only — no `export default`
- **Typed props** via `interface` — never skip prop types
- **Functional components** only — no class components
- **shadcn/ui** (Radix primitives + CVA) + **Tailwind CSS v4** for all UI primitives — never Ant Design, MUI, or Chakra
- **Lucide React** for icons
- **Loading states** — use `<Loader2 className="animate-spin" />` from lucide-react (or the shadcn `Skeleton` from `@/components/ui/skeleton`) centered with a flex wrapper

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
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';

const schema = z.object({
  email: z.string().email(),
  amount: z.number().positive(),
});

type FormData = z.infer<typeof schema>;

export const TransferForm: FC = () => {
  const form = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = (data: FormData) => {
    // use useApiMutation here
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit">Submit</Button>
      </form>
    </Form>
  );
};
```

## Notifications

```tsx
// In-app toast (sonner)
import { toast } from 'sonner';

toast.success('Record updated successfully');
toast.error('Something went wrong');

// Browser push notification (custom hook — wraps sonner + native Notification API)
import { useNotification } from '@kactus-bloom/ui/hooks';

const { sendBrowserNotification } = useNotification();
sendBrowserNotification('New Alert', 'Your report is ready.');
```

## Checklist

1. [ ] Component lives in `<Name>/` folder with `<Name>.tsx` + `index.ts`
2. [ ] Uses named export (no `export default`)
3. [ ] Props defined via `interface`
4. [ ] Uses `FC<Props>` typing
5. [ ] Uses shadcn/ui primitives from `@/components/ui/*`
6. [ ] Loading states handled with `<Loader2 className="animate-spin" />` (or `Skeleton`)
7. [ ] Added to `components/index.ts` barrel
8. [ ] Forms use React Hook Form + Zod
9. [ ] Tests written (see `testing.md`)
