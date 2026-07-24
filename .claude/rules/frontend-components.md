---
description: Component development patterns for kactus-bloom (shadcn/ui + Tailwind v4)
globs: ["packages/bloom-app/**/components/**", "packages/bloom-ui/**/components/**"]
---

# Component Development

> The frontend lives in the **`kactus-bloom`** repo. UI is **shadcn/ui (Radix + CVA) + Tailwind CSS v4**.

## Where components live
- **shadcn primitives** — `bloom-app/src/components/ui/` (lowercase files, generated
  shadcn recipe: `cva` variants + `@radix-ui/*` + `cn()` from `@/lib/utils`).
- **Feature components** — `bloom-app/src/modules/<name>/components/` (PascalCase).
- **Pages** — `bloom-app/src/modules/<name>/pages/` (PascalCase, e.g. `PortfolioListPage.tsx`).
- **Shared library** — `bloom-ui/src/components/<Name>/` (PascalCase folder + `index.ts` barrel).

## Pattern
```typescript
import { type FC } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Activity } from 'lucide-react';

interface MyComponentProps {
  title: string;
  value: number;
}

export const MyComponent: FC<MyComponentProps> = ({ title, value }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Activity className="h-4 w-4" /> {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-2xl font-bold tabular-nums">{value}</CardContent>
    </Card>
  );
};
```
- Named exports only; `FC<Props>`; style with Tailwind + `cn()`.
- Loading states: `<Skeleton />` from `@/components/ui/skeleton` or `<Loader2 className="animate-spin" />` (lucide-react).
- Forms: `react-hook-form` + `zod` via the shadcn `Form`/`FormField`/`FormItem`/`FormControl`/`FormMessage` wrapper.
- Modals: shadcn `Dialog`; dropdowns: shadcn `Select`. Toasts: `sonner` (`toast.success(...)`).

## Available shadcn primitives (`@/components/ui/*`)
`button` · `input` · `label` · `card` · `badge` · `skeleton` · `dialog` · `select` · `form` · `table` · `data-table`

## Shared library components (`@kactus-bloom/ui`)
- `AppLayout` — application shell (sidebar + header)
- `ChartCard` — card with an embedded Recharts chart (line/bar/area)
- `DataTable` — searchable, paginated table
- `ChatBox` — WebSocket chat widget
