import type React from 'react';

export type NavItemType = 'link' | 'dropdown';

/** Permission gate for a nav item / module, evaluated against the effective
 *  permissions (usePermissionEvaluator). Absent = always visible. Note: kactus
 *  has no permission call-site yet, so in practice `adminOnly` (superuser) and
 *  `debugOnly` are the live gates; this is threaded for completeness. */
export interface NavPermission {
  permission: string;
  action: 'read' | 'write' | 'manage';
}

export interface NavItem {
  id: string;
  /** Display label i18n key. Optional only for an untitled grouping dropdown;
   *  links always carry one. */
  labelKey?: string;
  path?: string;
  type: NavItemType;
  children?: NavItem[];
  /** Only shown when debug mode is active (admin only). */
  debugOnly?: boolean;
  /** Only shown to superusers. */
  adminOnly?: boolean;
  /** Render with extra weight (group-primary entry). */
  emphasized?: boolean;
  requiredPermission?: NavPermission;
}

export interface AppModuleDefinition {
  id: string;
  name: string;
  /** i18n key for the sidebar/breadcrumb label; falls back to `name`. */
  labelKey?: string;
  icon: React.ElementType;
  description: string;
  /** URL root — decouples the module id from its path (`portfolio`→`/portfolios`,
   *  `dashboard`→`/`). Defaults to `/{id}`. */
  basePath?: string;
  displayOrder?: number;
  navigation?: NavItem[];
  /** Only shown in the sidebar when debug mode is active (admin only). */
  debugOnly?: boolean;
  /** Only shown to superusers (sidebar + route are both gated elsewhere). */
  adminOnly?: boolean;
  /** Registered (routes work) but never shown in the sidebar. */
  sidebarHidden?: boolean;
  /** Every page under this module reads project-scoped data, so it is inert
   *  until a project is selected — shown disabled rather than hidden, and the
   *  route redirects to the project picker (see RequireProject). */
  requiresProject?: boolean;
  requiredPermission?: NavPermission;
}

export function defineAppModule(config: AppModuleDefinition): AppModuleDefinition {
  return config;
}

/** The module's URL root — `basePath` if set, else `/{id}`. */
export function moduleBasePath(m: Pick<AppModuleDefinition, 'id' | 'basePath'>): string {
  return m.basePath ?? `/${m.id}`;
}

export interface VisibilityCtx {
  can: (p: NavPermission) => boolean;
  isSuperuser: boolean;
  debug: boolean;
}

/** Shared nav-item visibility rule (mega-menu + moduleVisible). adminOnly and
 *  requiredPermission gate first; else the legacy debug gate applies. A link
 *  counts only with a path; a dropdown is visible only when ≥1 link child is
 *  visible (empty groups drop). */
export function navItemVisible(it: NavItem, ctx: VisibilityCtx): boolean {
  if (it.adminOnly && !ctx.isSuperuser) return false;
  const ownGate = it.requiredPermission
    ? ctx.can(it.requiredPermission)
    : !(it.debugOnly && !ctx.debug);
  if (!ownGate) return false;
  if (it.type === 'dropdown') {
    return (it.children ?? []).some((c) => c.type === 'link' && navItemVisible(c, ctx));
  }
  return !!it.path;
}

/** Sidebar visibility for a module. sidebarHidden always hides; adminOnly needs
 *  superuser; requiredPermission, when present, is the SOLE gate; else debugOnly
 *  applies, AND a module whose navigation has zero visible entries hides too. A
 *  module with no navigation is a flat link and stays visible. Route access is
 *  governed separately (AdminGuard for /admin). */
export function moduleVisible(
  mod: Pick<
    AppModuleDefinition,
    'sidebarHidden' | 'adminOnly' | 'requiredPermission' | 'debugOnly' | 'navigation'
  >,
  ctx: VisibilityCtx,
): boolean {
  if (mod.sidebarHidden) return false;
  if (mod.adminOnly && !ctx.isSuperuser) return false;
  if (mod.requiredPermission) return ctx.can(mod.requiredPermission);
  if (mod.debugOnly && !ctx.debug) return false;
  if (!mod.navigation || mod.navigation.length === 0) return true;
  return mod.navigation.some((it) => navItemVisible(it, ctx));
}
