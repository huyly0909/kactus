import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Settings, ChevronDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet';
import { Popover, PopoverAnchor, PopoverContent } from '@/components/ui/popover';
import { useSortedModules } from '@/layouts/components/useSortedModules';
import { ActiveProjectChip } from '@/layouts/components/ActiveProjectChip';
import { useNavStore } from '@/store/navStore';
import { useProjectStore } from '@/store/projectStore';
import { useIsAdmin } from '@/hooks/useIsAdmin';
import { usePermissionEvaluator } from '@/modules/core/auth/access';
import { useDebugMode } from '@/hooks/useDebugMode';
import { useMediaQuery } from '@/hooks/use-media-query';
import type { AppModule } from '@/registry';
import {
  moduleBasePath,
  moduleVisible,
  navItemVisible,
  type NavItem,
  type VisibilityCtx,
} from '@/lib/module-core';

// Rows come in two palettes. Inside the sidebar chrome (bg-sidebar) they use the
// --sidebar* tokens so active/hover cues read correctly on every theme preset;
// the mega-menu popover renders on bg-popover (portaled out of the sidebar), so
// its rows use the global primary/accent tokens instead.
const ROW_BASE =
  'group flex items-center w-full text-left rounded-md transition-all duration-150 ease-in-out active:scale-[0.98] outline-none cursor-pointer';
const SIDE_ACTIVE = 'bg-sidebar-accent text-sidebar-accent-foreground font-semibold';
const SIDE_INACTIVE =
  'text-sidebar-foreground/80 font-medium hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground';
const MENU_ACTIVE = 'bg-primary/10 text-primary font-semibold';
const MENU_INACTIVE = 'text-muted-foreground font-medium hover:bg-accent/60 hover:text-foreground';
const ICON_BASE = 'w-[18px] h-[18px] shrink-0';

function moduleLabel(module: AppModule, t: (k: string) => string): string {
  return module.labelKey ? t(module.labelKey) : module.name;
}

function isPathActive(currentPathname: string, target: string): boolean {
  return currentPathname === target || currentPathname.startsWith(`${target}/`);
}

function isModuleActive(base: string, pathname: string): boolean {
  return base === '/' ? pathname === '/' : isPathActive(pathname, base);
}

export function ModuleSidebar() {
  const { t } = useTranslation();
  const location = useLocation();
  const sortedModules = useSortedModules();
  const debug = useDebugMode();
  const can = usePermissionEvaluator();
  const isSuperuser = useIsAdmin();
  const ctx: VisibilityCtx = { can, isSuperuser, debug };
  const hasProject = useProjectStore((s) => s.currentProject !== null);

  // Mobile drawer — the desktop <aside> and the mobile <Sheet> render the same
  // nav body; the hamburger in TopHeader toggles this store.
  const navOpen = useNavStore((s) => s.open);
  const setNavOpen = useNavStore((s) => s.setOpen);
  const closeNav = useNavStore((s) => s.close);

  const activeModule = sortedModules.find((m) =>
    isModuleActive(moduleBasePath(m), location.pathname),
  );
  const activeModuleId = activeModule?.id ?? null;

  // One mega-menu open at a time, on hover, with a grace timer so the cursor can
  // transit trigger → popover without the menu collapsing.
  const [openModuleId, setOpenModuleId] = useState<string | null>(null);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelPendingClose = useCallback(() => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  }, []);
  const scheduleClose = useCallback(() => {
    cancelPendingClose();
    closeTimerRef.current = setTimeout(() => setOpenModuleId(null), 150);
  }, [cancelPendingClose]);
  const openMenu = useCallback(
    (id: string) => {
      cancelPendingClose();
      setOpenModuleId((prev) => (prev === id ? prev : id));
    },
    [cancelPendingClose],
  );
  const closeMenu = useCallback(() => {
    cancelPendingClose();
    setOpenModuleId(null);
  }, [cancelPendingClose]);

  useEffect(() => () => cancelPendingClose(), [cancelPendingClose]);
  // Close the mobile drawer on navigation.
  useEffect(() => closeNav(), [location.pathname, closeNav]);

  // Touch devices have no hover, so the hover-opened mega-menu is unreachable —
  // render inline accordion submenus instead. One module expanded at a time; the
  // active module starts expanded.
  const coarseNav = useMediaQuery('(pointer: coarse)');
  const [expandedModuleId, setExpandedModuleId] = useState<string | null>(activeModuleId);
  // Adjust-during-render: when navigation lands in another module, follow it.
  const [prevModuleId, setPrevModuleId] = useState(activeModuleId);
  if (prevModuleId !== activeModuleId) {
    setPrevModuleId(activeModuleId);
    setExpandedModuleId(activeModuleId);
  }

  const settingsActive = location.pathname.startsWith('/settings');

  const body = (
    <div className="flex h-full min-h-0 w-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="h-14 shrink-0 flex items-center border-b border-sidebar-border px-4">
        <span className="text-lg font-bold tracking-tight text-foreground">Kactus</span>
      </div>

      <ScrollArea className="flex-1">
        <nav className="p-2 flex flex-col gap-0.5">
          {sortedModules
            .filter((mod) => moduleVisible(mod, ctx))
            .map((mod) =>
              mod.requiresProject && !hasProject ? (
                <DisabledModuleRow key={mod.id} module={mod} />
              ) : coarseNav ? (
                <AccordionModuleNode
                  key={mod.id}
                  module={mod}
                  currentPathname={location.pathname}
                  expanded={expandedModuleId === mod.id}
                  onToggle={() => setExpandedModuleId((prev) => (prev === mod.id ? null : mod.id))}
                  ctx={ctx}
                />
              ) : (
                <ModuleNode
                  key={mod.id}
                  module={mod}
                  currentPathname={location.pathname}
                  isMenuOpen={openModuleId === mod.id}
                  onMenuOpen={openMenu}
                  onMenuClose={closeMenu}
                  onMenuScheduleClose={scheduleClose}
                  onMenuCancelClose={cancelPendingClose}
                  ctx={ctx}
                />
              ),
            )}

          <div className="my-1.5 h-px bg-sidebar-border/60" />

          <FlatLink
            to="/settings/profile"
            icon={Settings}
            label={t('settings.title')}
            active={settingsActive}
          />
        </nav>
      </ScrollArea>

      <div className="shrink-0 border-t border-sidebar-border p-2">
        <ActiveProjectChip />
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop: persistent sidebar (hidden below md). */}
      <aside className="hidden md:flex h-full shrink-0 w-60 border-r border-sidebar-border flex-col">
        {body}
      </aside>
      {/* Mobile: same nav body in a left drawer, toggled from TopHeader. */}
      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetContent
          side="left"
          showCloseButton={false}
          className="w-60 max-w-[80vw] p-0 flex flex-col gap-0"
        >
          <SheetTitle className="sr-only">{t('layout.navigation')}</SheetTitle>
          {body}
        </SheetContent>
      </Sheet>
    </>
  );
}

interface FlatLinkProps {
  to: string;
  icon: React.ElementType;
  label: string;
  active: boolean;
}

function FlatLink({ to, icon: Icon, label, active }: FlatLinkProps) {
  return (
    <Link
      to={to}
      data-active={active}
      className={cn(ROW_BASE, active ? SIDE_ACTIVE : SIDE_INACTIVE, 'px-3 py-2 text-sm gap-3')}
    >
      <Icon className={ICON_BASE} />
      <span className="truncate">{label}</span>
    </Link>
  );
}

interface ModuleNodeProps {
  module: AppModule;
  currentPathname: string;
  isMenuOpen: boolean;
  onMenuOpen: (id: string) => void;
  onMenuClose: () => void;
  onMenuScheduleClose: () => void;
  onMenuCancelClose: () => void;
  ctx: VisibilityCtx;
}

function ModuleNode({
  module,
  currentPathname,
  isMenuOpen,
  onMenuOpen,
  onMenuClose,
  onMenuScheduleClose,
  onMenuCancelClose,
  ctx,
}: ModuleNodeProps) {
  const { t } = useTranslation();
  const Icon = module.icon;
  const moduleRoot = moduleBasePath(module);
  const isActive = isModuleActive(moduleRoot, currentPathname);
  const hasMenu = (module.navigation?.length ?? 0) > 0;

  if (!hasMenu) {
    return <ModuleLeafLink module={module} isActive={isActive} />;
  }

  return (
    <Popover open={isMenuOpen} onOpenChange={(o) => (o ? onMenuOpen(module.id) : onMenuClose())}>
      <PopoverAnchor asChild>
        <Link
          to={moduleRoot}
          data-active={isActive}
          data-state={isMenuOpen ? 'open' : 'closed'}
          onMouseEnter={() => onMenuOpen(module.id)}
          onMouseLeave={onMenuScheduleClose}
          onClick={onMenuClose}
          className={cn(
            ROW_BASE,
            isActive ? SIDE_ACTIVE : SIDE_INACTIVE,
            'justify-start px-3 py-2 text-sm gap-3 h-auto',
            !isActive &&
              'data-[state=open]:bg-sidebar-accent/50 data-[state=open]:text-sidebar-accent-foreground',
          )}
        >
          <Icon className={cn(ICON_BASE, module.debugOnly && !isActive && 'text-debug')} />
          <span className="truncate">{moduleLabel(module, t)}</span>
        </Link>
      </PopoverAnchor>
      <PopoverContent
        onMouseEnter={onMenuCancelClose}
        onMouseLeave={onMenuScheduleClose}
        onOpenAutoFocus={(e) => e.preventDefault()}
        side="right"
        align="start"
        sideOffset={8}
        collisionPadding={12}
        className="w-auto max-w-[80vw] max-h-[calc(100vh-80px)] overflow-y-auto p-0 rounded-lg shadow-lg"
      >
        <MegaMenu
          module={module}
          moduleRoot={moduleRoot}
          currentPathname={currentPathname}
          onSelect={onMenuClose}
          ctx={ctx}
        />
      </PopoverContent>
    </Popover>
  );
}

// A `requiresProject` module with nothing selected. Shown rather than hidden:
// the entries are the app's main navigation, and a sidebar that silently loses
// half its rows reads as a broken build, not as "pick a project first".
function DisabledModuleRow({ module }: { module: AppModule }) {
  const { t } = useTranslation();
  const Icon = module.icon;
  return (
    <div
      aria-disabled
      title={t('projects.requires_selection')}
      className={cn(
        ROW_BASE,
        'px-3 py-2 text-sm gap-3 text-sidebar-foreground/35 cursor-not-allowed active:scale-100',
      )}
    >
      <Icon className={ICON_BASE} />
      <span className="truncate">{moduleLabel(module, t)}</span>
    </div>
  );
}

function ModuleLeafLink({ module, isActive }: { module: AppModule; isActive: boolean }) {
  const { t } = useTranslation();
  const Icon = module.icon;
  return (
    <Link
      to={moduleBasePath(module)}
      data-active={isActive}
      className={cn(ROW_BASE, isActive ? SIDE_ACTIVE : SIDE_INACTIVE, 'px-3 py-2 text-sm gap-3')}
    >
      <Icon className={cn(ICON_BASE, module.debugOnly && !isActive && 'text-debug')} />
      <span className="truncate">{moduleLabel(module, t)}</span>
    </Link>
  );
}

interface AccordionModuleNodeProps {
  module: AppModule;
  currentPathname: string;
  expanded: boolean;
  onToggle: () => void;
  ctx: VisibilityCtx;
}

// Touch counterpart of ModuleNode: the row toggles an inline accordion instead
// of opening a hover popover. The module overview stays reachable as the first
// sub-link.
function AccordionModuleNode({
  module,
  currentPathname,
  expanded,
  onToggle,
  ctx,
}: AccordionModuleNodeProps) {
  const { t } = useTranslation();
  const Icon = module.icon;
  const moduleRoot = moduleBasePath(module);
  const isActive = isModuleActive(moduleRoot, currentPathname);

  if ((module.navigation?.length ?? 0) === 0) {
    return <ModuleLeafLink module={module} isActive={isActive} />;
  }

  const model = buildMegaModel(module.navigation, moduleRoot, ctx);
  const overviewActive = currentPathname === moduleRoot;

  return (
    <div className="flex flex-col">
      <Link
        to={moduleRoot}
        aria-expanded={expanded}
        data-active={isActive}
        onClick={(e) => {
          e.preventDefault();
          onToggle();
        }}
        className={cn(
          ROW_BASE,
          isActive ? SIDE_ACTIVE : SIDE_INACTIVE,
          'justify-start px-3 py-2 text-sm gap-3',
        )}
      >
        <Icon className={cn(ICON_BASE, module.debugOnly && !isActive && 'text-debug')} />
        <span className="truncate">{moduleLabel(module, t)}</span>
        <ChevronDown
          className={cn(
            'w-4 h-4 shrink-0 ml-auto opacity-50 transition-transform duration-150',
            expanded && 'rotate-180',
          )}
        />
      </Link>
      {expanded && (
        <div className="ml-5 pl-2 border-l border-sidebar-border/50 flex flex-col gap-0.5 py-1">
          <Link
            to={moduleRoot}
            data-active={overviewActive}
            aria-current={overviewActive ? 'page' : undefined}
            className={cn(
              ROW_BASE,
              overviewActive ? SIDE_ACTIVE : SIDE_INACTIVE,
              'px-3 py-2 text-[0.8125rem]',
            )}
          >
            <span className="truncate">{t('layout.overview')}</span>
          </Link>
          {model.columns.map((col) => (
            <div key={col.id} className="flex flex-col gap-0.5">
              {col.title && (
                <div className="px-3 pt-2 pb-1 text-[0.625rem] font-semibold uppercase tracking-wider text-sidebar-foreground/60">
                  {t(col.title)}
                </div>
              )}
              {col.links.map((link) => {
                const active = isPathActive(currentPathname, link.path);
                return (
                  <Link
                    key={link.id}
                    to={link.path}
                    data-active={active}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      ROW_BASE,
                      active ? SIDE_ACTIVE : SIDE_INACTIVE,
                      'px-3 py-2 text-[0.8125rem]',
                      link.emphasized && !active && 'font-semibold text-sidebar-accent-foreground',
                    )}
                  >
                    <span className="truncate">{t(link.labelKey)}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface MegaColumn {
  id: string;
  title: string | null;
  links: { id: string; labelKey: string; path: string; emphasized?: boolean }[];
}

interface MegaMenuModel {
  columns: MegaColumn[];
  hasTitledColumn: boolean;
}

function buildMegaModel(
  items: NavItem[] | undefined,
  moduleRoot: string,
  ctx: VisibilityCtx,
): MegaMenuModel {
  const cols: MegaColumn[] = [];
  const extraTopLinks: MegaColumn['links'] = [];

  for (const item of items ?? []) {
    if (!navItemVisible(item, ctx)) continue;

    if (item.type === 'link' && item.path) {
      // Skip the module-root link — the sidebar trigger navigates there already.
      if (item.path !== moduleRoot) {
        extraTopLinks.push({
          id: item.id,
          labelKey: item.labelKey ?? '',
          path: item.path,
          emphasized: item.emphasized,
        });
      }
    } else if (item.type === 'dropdown') {
      const links = (item.children ?? [])
        .filter(
          (c): c is NavItem & { path: string } =>
            c.type === 'link' && !!c.path && navItemVisible(c, ctx),
        )
        .map((c) => ({
          id: c.id,
          labelKey: c.labelKey ?? '',
          path: c.path,
          emphasized: c.emphasized,
        }));
      if (links.length > 0) cols.push({ id: item.id, title: item.labelKey ?? null, links });
    }
  }

  if (extraTopLinks.length > 0) {
    cols.unshift({ id: '_general', title: null, links: extraTopLinks });
  }

  return { columns: cols, hasTitledColumn: cols.some((c) => c.title !== null) };
}

interface MegaMenuProps {
  module: AppModule;
  moduleRoot: string;
  currentPathname: string;
  onSelect: () => void;
  ctx: VisibilityCtx;
}

function MegaMenu({ module, moduleRoot, currentPathname, onSelect, ctx }: MegaMenuProps) {
  const { t } = useTranslation();
  const model = buildMegaModel(module.navigation, moduleRoot, ctx);

  return (
    <div className="flex p-3 gap-3">
      {model.columns.map((col, idx) => {
        const groupActive = col.links.some((l) => isPathActive(currentPathname, l.path));
        return (
          <div
            key={col.id}
            className={cn(
              'flex flex-col min-w-36 shrink-0',
              idx > 0 && 'border-l border-border/40 pl-3',
            )}
          >
            {col.title ? (
              <div
                className={cn(
                  'px-3 py-1.5 text-[0.625rem] font-semibold uppercase tracking-wider',
                  groupActive ? 'text-primary' : 'text-muted-foreground/70',
                )}
              >
                {t(col.title)}
              </div>
            ) : model.hasTitledColumn ? (
              <div className="py-1.5" aria-hidden />
            ) : null}
            <div className="flex flex-col gap-0.5">
              {col.links.map((link) => {
                const active = isPathActive(currentPathname, link.path);
                return (
                  <Link
                    key={link.id}
                    to={link.path}
                    onClick={onSelect}
                    data-active={active}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      ROW_BASE,
                      active ? MENU_ACTIVE : MENU_INACTIVE,
                      'px-3 py-1.5 text-[0.8125rem]',
                      link.emphasized && !active && 'font-semibold text-foreground',
                    )}
                  >
                    <span className="truncate">{t(link.labelKey)}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
