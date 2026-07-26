import { useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SYSTEM_MODULES } from '@/registry';
import { moduleBasePath, type NavItem } from '@/lib/module-core';
import { useBreadcrumbScope } from '@/layouts/components/BreadcrumbScope';

export interface BreadcrumbCrumb {
  label: string;
  to?: string;
}

// Walks a module's navigation tree for the deepest node whose `path` is a prefix
// of the current pathname — so the breadcrumb reads "Module › Sub-page".
function findDeepestMatch(items: NavItem[], pathname: string): NavItem | null {
  let best: NavItem | null = null;
  let bestLen = 0;
  const walk = (item: NavItem) => {
    if (item.type === 'link' && item.path) {
      if (pathname === item.path || pathname.startsWith(`${item.path}/`)) {
        if (item.path.length > bestLen) {
          best = item;
          bestLen = item.path.length;
        }
      }
    }
    if (item.type === 'dropdown' && item.children) {
      for (const c of item.children) walk(c);
    }
  };
  for (const i of items) walk(i);
  return best;
}

export function useBreadcrumb(): BreadcrumbCrumb[] {
  const { t } = useTranslation();
  const location = useLocation();
  const { leaf } = useBreadcrumbScope();

  return useMemo(() => {
    const pathname = location.pathname;
    const segments = pathname.split('/').filter(Boolean);

    // Settings is not a registry module — hand-rolled trail.
    if (segments[0] === 'settings') {
      const crumbs: BreadcrumbCrumb[] = [{ label: t('settings.title'), to: '/settings/profile' }];
      const tab = segments[1];
      if (tab && tab !== 'profile') {
        crumbs.push({ label: t(`settings.${tab}`), to: `/settings/${tab}` });
      }
      if (leaf) crumbs.push({ label: leaf });
      return crumbs;
    }

    // Deepest matching nav link across ALL modules (a page's URL may be owned by
    // one module while its nav entry lives in another). Longest path wins.
    let ownerMod: (typeof SYSTEM_MODULES)[number] | undefined;
    let navLeaf: NavItem | null = null;
    let bestLen = -1;
    for (const m of SYSTEM_MODULES) {
      if (!m.navigation) continue;
      const match = findDeepestMatch(m.navigation, pathname);
      if (match?.path && match.path.length > bestLen) {
        ownerMod = m;
        navLeaf = match;
        bestLen = match.path.length;
      }
    }

    const rootMod =
      ownerMod ??
      SYSTEM_MODULES.find((m) => {
        const base = moduleBasePath(m);
        return base === '/'
          ? pathname === '/'
          : pathname === base || pathname.startsWith(`${base}/`);
      });
    if (!rootMod) return [{ label: segments[0] ?? '' }];

    const crumbs: BreadcrumbCrumb[] = [
      { label: rootMod.labelKey ? t(rootMod.labelKey) : rootMod.name, to: moduleBasePath(rootMod) },
    ];
    if (navLeaf?.labelKey) crumbs.push({ label: t(navLeaf.labelKey), to: navLeaf.path });
    if (leaf) crumbs.push({ label: leaf });

    return crumbs;
  }, [location.pathname, t, leaf]);
}
