import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Plus, FolderKanban, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useProjects } from '@/hooks/useProjectQuery';
import { useProjectStore } from '@/store/projectStore';
import { useAuthStore } from '@/store/authStore';
import type { Project } from '@/types/project';
import { CreateProjectDialog } from '@modules/project/components/CreateProjectDialog';

export function ProjectListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const { data, isLoading } = useProjects();
  const user = useAuthStore((s) => s.user);
  const currentProject = useProjectStore((s) => s.currentProject);
  const setProject = useProjectStore((s) => s.setProject);
  const [dialogOpen, setDialogOpen] = useState(false);

  const projects = data?.items ?? [];

  const handleSelect = (e: React.MouseEvent, project: Project) => {
    e.stopPropagation();
    setProject(project);
    // Everything else is project-scoped — drop cached data so it refetches for
    // the newly selected project (the cookie the request now carries changed).
    void qc.invalidateQueries();
    toast.success(t('projects.selected', { name: project.name }));
    // Arrived here because a project-scoped route sent us (RequireProject)?
    // Picking one answers that question — go back to what they asked for.
    const from = (location.state as { from?: { pathname: string } } | null)?.from;
    if (from?.pathname) navigate(from.pathname, { replace: true });
  };

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('projects.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('projects.subtitle')}</p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="mr-1 h-4 w-4" />
          {t('projects.create_title')}
        </Button>
      </div>

      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      )}

      {!isLoading && projects.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16 text-center">
          <FolderKanban className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t('projects.empty')}</p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((p) => {
          const isActive = currentProject?.id === p.id;
          // Heuristic OWNER tag: the creator is the owner (true for personal
          // projects and any you created). The authoritative role lives on the
          // detail page's members list.
          const owned = !!user && p.created_by === user.id;
          return (
            <Card
              key={p.id}
              className={
                'cursor-pointer transition-colors hover:border-primary/50' +
                (isActive ? ' border-primary ring-1 ring-primary/40' : '')
              }
              onClick={() => navigate(`/projects/${p.id}`)}
            >
              <CardHeader>
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-base">{p.name}</CardTitle>
                  <div className="flex shrink-0 items-center gap-1">
                    {owned && <Badge variant="secondary">{t('projects.owner_tag')}</Badge>}
                    {isActive && (
                      <Badge className="gap-1">
                        <Check className="h-3 w-3" />
                        {t('projects.active_tag')}
                      </Badge>
                    )}
                  </div>
                </div>
                <CardDescription className="font-mono text-xs">{p.code}</CardDescription>
              </CardHeader>
              <CardContent className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  {p.description || t('projects.no_description')}
                </span>
                <Button
                  size="sm"
                  variant={isActive ? 'secondary' : 'outline'}
                  disabled={isActive}
                  onClick={(e) => handleSelect(e, p)}
                >
                  {isActive ? t('projects.current') : t('projects.select')}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <CreateProjectDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}
