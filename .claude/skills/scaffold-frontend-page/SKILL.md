---
name: scaffold-frontend-page
description: Create a new page in usonia-app with routing and nav registration
user_invocable: true
---

# Scaffold a new frontend page

Create a new page for the Usonia frontend dashboard.

## Steps

1. Create page directory and component:
   - `frontend/packages/usonia-app/src/pages/<PageName>/index.tsx`
   - Use `FC` with named export
   - Import from `@usonia/ui` for shared components

2. Register route in `frontend/packages/usonia-app/src/router/index.tsx`:
   - Add import for the new page
   - Add `<Route path="/<page-path>" element={<PageName />} />` inside ConfigGuard + MainLayout

3. Add nav item to `frontend/packages/usonia-app/src/layouts/MainLayout.tsx`:
   - Add to appropriate `navSections` array
   - Choose a Lucide icon

4. Create test file (optional):
   - `frontend/packages/usonia-app/src/pages/<PageName>/<PageName>.test.tsx`

## Conventions
- Named exports only, `FC<Props>`
- Use `useApiQuery` for data fetching
- Use `useConfigStore` for project_id/document_id
- Mantine for UI, Lucide for icons
