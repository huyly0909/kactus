import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { useAdminProjects } from '@/hooks/useAdminQuery';
import type { Project } from '@/types/project';

/** Read-only list of every project in the system (superuser only). */
export function AdminProjectsPage() {
  const { t } = useTranslation();
  const { data, isLoading } = useAdminProjects();

  const columns: DataTableColumn<Project>[] = [
    { key: 'name', title: t('admin.projects.name'), className: 'font-medium' },
    {
      key: 'code',
      title: t('admin.projects.code'),
      render: (p) => <code className="font-mono text-xs text-muted-foreground">{p.code}</code>,
    },
    {
      key: 'description',
      title: t('admin.projects.description'),
      render: (p) => <span className="text-muted-foreground">{p.description || '—'}</span>,
    },
    {
      key: 'status',
      title: t('admin.projects.status'),
      render: (p) => (
        <Badge variant={p.status === 'active' ? 'success' : 'secondary'}>{p.status}</Badge>
      ),
    },
  ];

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">{t('admin.projects.title')}</h1>
        <p className="text-sm text-muted-foreground">{t('admin.projects.subtitle')}</p>
      </div>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        searchable
        searchPlaceholder={t('common.search')}
        emptyMessage={t('admin.projects.empty')}
        getRowKey={(p) => p.id}
      />
    </div>
  );
}
