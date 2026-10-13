import { type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Check, ChevronsUpDown, FolderKanban, Globe } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useProjects } from '@/hooks/useProjectQuery';
import { useIsAdmin } from '@/hooks/useIsAdmin';
import { projectDisplayName } from '@/lib/project';
import { useProjectStore } from '@/store/projectStore';

/**
 * The active project, pinned to the bottom of the sidebar: what you are scoped
 * to, always on screen and one click from being changed.
 *
 * A dropdown, not a dialog — switching is the only action here, and a modal
 * around a single list is a heavy wrapper for it. The chip shows the plain
 * `name` because the display name (`name <code>`) truncates at sidebar width;
 * the full identity lives in the tooltip and in the menu items.
 *
 * Nothing is edited here. That happens on `/projects/:id`, where you can act on
 * any project you belong to rather than only the selected one.
 */
export const ActiveProjectChip: FC = () => {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const isSuperuser = useIsAdmin();
  const { data } = useProjects();
  const currentProject = useProjectStore((s) => s.currentProject);
  const setProject = useProjectStore((s) => s.setProject);
  const clearProject = useProjectStore((s) => s.clearProject);

  const projects = data?.items ?? [];
  // The store's copy is written at switch time; prefer the freshly fetched row
  // so a rename made elsewhere shows here without a re-login.
  const active = projects.find((p) => p.id === currentProject?.id) ?? currentProject;

  const label = active
    ? active.name
    : isSuperuser
      ? t('projects.all_projects')
      : t('projects.none_selected');
  const Icon = active ? FolderKanban : Globe;

  // Everything else is project-scoped: the cookie the requests carry just
  // changed, so every cached entry belongs to the previous project.
  const invalidate = () => void qc.invalidateQueries();

  const handleSelect = (id: string) => {
    const next = projects.find((p) => p.id === id);
    if (!next || next.id === active?.id) return;
    setProject(next);
    toast.success(t('projects.selected', { name: projectDisplayName(next) }));
    invalidate();
  };

  return (
    <DropdownMenu>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger
            aria-label={t('projects.switch_label')}
            className={cn(
              'group flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm',
              'text-sidebar-foreground/80 font-medium outline-none transition-colors',
              'hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
            )}
          >
            <Icon className="h-[18px] w-[18px] shrink-0" />
            <span className="truncate">{label}</span>
            <ChevronsUpDown className="ml-auto h-4 w-4 shrink-0 opacity-50" />
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent side="right">{active ? projectDisplayName(active) : label}</TooltipContent>
      </Tooltip>

      <DropdownMenuContent align="start" side="top" className="w-64">
        <DropdownMenuLabel>{t('projects.switch_label')}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {projects.map((p) => (
          <DropdownMenuItem
            key={p.id}
            className="cursor-pointer"
            onSelect={() => handleSelect(p.id)}
          >
            <Check className={cn('h-4 w-4', p.id !== active?.id && 'opacity-0')} />
            <span className="truncate">{projectDisplayName(p)}</span>
          </DropdownMenuItem>
        ))}
        {isSuperuser && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="cursor-pointer"
              onSelect={() => {
                clearProject();
                invalidate();
              }}
            >
              <Check className={cn('h-4 w-4', active && 'opacity-0')} />
              <span>{t('projects.all_projects')}</span>
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
