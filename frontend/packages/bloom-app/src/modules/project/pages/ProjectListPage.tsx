import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Check, Crown, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DataTable,
  type DataTableColumn,
  type DataTableFilterChip,
} from '@/components/ui/data-table';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useFormatDateTime } from '@/hooks/useFormatDateTime';
import { useProjects } from '@/hooks/useProjectQuery';
import {
  filterAndSortProjects,
  isProjectOwner,
  projectDisplayName,
  projectMemberCount,
  type ProjectStatusFilter,
} from '@/lib/project';
import { useProjectStore } from '@/store/projectStore';
import type { Project } from '@/types/project';
import { CreateProjectDialog } from '@modules/project/components/CreateProjectDialog';
import { ProjectOwner } from '@modules/project/components/ProjectOwner';

const STATUS_OPTIONS: ProjectStatusFilter[] = ['active', 'archived', 'all'];

/**
 * Projects you belong to, as a dataview.
 *
 * Two different "active" ideas share the screen, so they are kept visually
 * apart: the leading check icon marks the **current** project (the one the
 * `kactus_project_id` cookie scopes your data to), while the status filter is
 * about a project's lifecycle and hides archived ones by default.
 *
 * Clicking a row navigates to `/projects/:id`; switching is the explicit button,
 * so reading about a project never silently re-scopes the whole app.
 */
export function ProjectListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const fmtDateTime = useFormatDateTime();
  const { data, isLoading } = useProjects();
  const currentProject = useProjectStore((s) => s.currentProject);
  const setProject = useProjectStore((s) => s.setProject);

  const [createOpen, setCreateOpen] = useState(false);
  const [status, setStatus] = useState<ProjectStatusFilter>('active');

  const rows = useMemo(() => filterAndSortProjects(data?.items ?? [], status), [data, status]);

  const chips: DataTableFilterChip[] = [];
  if (status !== 'all') {
    chips.push({
      id: 'status',
      label: `${t('projects.col_status')}: ${t(`projects.status_${status}`)}`,
      onRemove: () => setStatus('all'),
    });
  }

  const handleSelect = (e: React.MouseEvent, project: Project) => {
    e.stopPropagation();
    setProject(project);
    // Everything else is project-scoped — drop cached data so it refetches for
    // the newly selected project (the cookie the request now carries changed).
    void qc.invalidateQueries();
    toast.success(t('projects.selected', { name: projectDisplayName(project) }));
    // Arrived here because a project-scoped route sent us (RequireProject)?
    // Picking one answers that question — go back to what they asked for.
    const from = (location.state as { from?: { pathname: string } } | null)?.from;
    if (from?.pathname) navigate(from.pathname, { replace: true });
  };

  const columns: DataTableColumn<Project>[] = [
    {
      key: 'is_current',
      title: '',
      align: 'center',
      hideable: false,
      menuLabel: t('projects.col_current'),
      exportValue: (p) => (currentProject?.id === p.id ? 'yes' : ''),
      render: (p) =>
        currentProject?.id === p.id ? (
          <Check className="mx-auto h-4 w-4 text-primary" aria-label={t('projects.col_current')} />
        ) : null,
    },
    {
      key: 'id',
      title: t('projects.col_id'),
      defaultHidden: true,
      render: (p) => <span className="font-mono text-xs text-muted-foreground">{p.id}</span>,
    },
    {
      key: 'code',
      title: t('projects.col_code'),
      sortable: true,
      render: (p) => <code className="font-mono text-xs">{p.code}</code>,
    },
    { key: 'name', title: t('projects.col_name'), className: 'font-medium', sortable: true },
    {
      key: 'is_owner',
      title: t('projects.col_owner'),
      align: 'center',
      exportValue: (p) => (isProjectOwner(p) ? 'yes' : ''),
      render: (p) =>
        isProjectOwner(p) ? (
          <Crown className="mx-auto h-4 w-4 text-primary" aria-label={t('projects.owner_tag')} />
        ) : null,
    },
    {
      key: 'owner_name',
      title: t('projects.col_owner_name'),
      sortable: true,
      // The CSV must not carry the creator's name for an unassigned project —
      // that is the exact conflation `has_owner` exists to prevent.
      exportValue: (p) =>
        p.has_owner ? (p.owner_name ?? p.owner_email ?? '') : t('projects.owner_unassigned'),
      render: (p) => <ProjectOwner project={p} className="text-muted-foreground" />,
    },
    {
      key: 'member_count',
      title: t('projects.col_members'),
      align: 'right',
      className: 'tabular-nums',
      sortable: true,
      sortAccessor: projectMemberCount,
      render: projectMemberCount,
    },
    {
      key: 'create_time',
      title: t('projects.col_created'),
      sortable: true,
      sortAccessor: (p) => p.create_time ?? '',
      render: (p) => (
        <span className="whitespace-nowrap text-muted-foreground">
          {fmtDateTime(p.create_time)}
        </span>
      ),
    },
    {
      key: 'actions',
      title: '',
      align: 'right',
      hideable: false,
      render: (p) => {
        const isCurrent = currentProject?.id === p.id;
        return (
          <Button
            size="sm"
            variant={isCurrent ? 'secondary' : 'outline'}
            disabled={isCurrent}
            onClick={(e) => handleSelect(e, p)}
          >
            {isCurrent ? t('projects.current') : t('projects.select')}
          </Button>
        );
      },
    },
  ];

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('projects.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('projects.subtitle')}</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-1 h-4 w-4" />
          {t('projects.create_title')}
        </Button>
      </div>

      <div className="mb-4 flex items-end gap-2">
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">{t('projects.col_status')}</Label>
          <Select value={status} onValueChange={(v) => setStatus(v as ProjectStatusFilter)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((s) => (
                <SelectItem key={s} value={s}>
                  {t(`projects.status_${s}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={rows}
        loading={isLoading}
        searchable
        searchPlaceholder={t('common.search')}
        emptyMessage={t('projects.empty')}
        getRowKey={(p) => p.id}
        onRowClick={(p) => navigate(`/projects/${p.id}`)}
        filterChips={chips}
        enableColumnVisibility
        enableExport
        exportFilename="projects.csv"
      />

      <CreateProjectDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
