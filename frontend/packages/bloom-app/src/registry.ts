import type { AppModuleDefinition } from '@/lib/module-core';

export type AppModule = AppModuleDefinition;

// Dynamic scan: every module manifest at modules/<m>/index.ts (and the core
// modules at modules/core/<m>/index.ts). Adding a module = dropping in an
// index.ts that default-exports defineAppModule(...) — no central edit.
const rawModules = import.meta.glob(['./modules/*/index.ts', './modules/core/*/index.ts'], {
  eager: true,
}) as Record<string, { default: AppModuleDefinition }>;

export const SYSTEM_MODULES: AppModule[] = Object.values(rawModules)
  .map((m) => m.default)
  .sort((a, b) => (a.displayOrder ?? 99) - (b.displayOrder ?? 99));
