import { SYSTEM_MODULES, type AppModule } from '@/registry';

// Module ordering for the sidebar. Builtiful cascaded user/company/workspace
// preferences here; kactus has none of that, so the registry's displayOrder
// sort (already applied in registry.ts) is the whole story. Kept as a hook so
// the sidebar has a single seam if per-user ordering ever lands.
export function useSortedModules(): AppModule[] {
  return SYSTEM_MODULES;
}
