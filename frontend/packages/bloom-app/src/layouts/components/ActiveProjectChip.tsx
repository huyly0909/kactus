import { useEffect, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { FolderKanban, ChevronsUpDown, Globe } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useProjects, useUpdateProject } from '@/hooks/useProjectQuery';
import { useIsAdmin } from '@/hooks/useIsAdmin';
import { useProjectStore } from '@/store/projectStore';

/** Sentinel for the admin-only unscoped view — Radix Select rejects "". */
const ALL_PROJECTS = '__all__';

/**
 * The active project, pinned to the bottom of the sidebar. Clicking it opens the
 * switcher plus the project's own detail form, so the thing you are scoped to is
 * always on screen and always one click from being changed or renamed.
 */
export const ActiveProjectChip: FC = () => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const currentProject = useProjectStore((s) => s.currentProject);
  const isSuperuser = useIsAdmin();

  const label =
    currentProject?.name ??
    (isSuperuser ? t('projects.all_projects') : t('projects.none_selected'));
  const Icon = currentProject ? FolderKanban : Globe;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t('projects.active_project')}
        className={cn(
          'group flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm',
          'text-sidebar-foreground/80 font-medium outline-none transition-colors',
          'hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
        )}
      >
        <Icon className="h-[18px] w-[18px] shrink-0" />
        <span className="flex min-w-0 flex-col">
          <span className="text-[10px] uppercase tracking-wide text-sidebar-foreground/50">
            {t('projects.active_project')}
          </span>
          <span className="truncate">{label}</span>
        </span>
        <ChevronsUpDown className="ml-auto h-4 w-4 shrink-0 opacity-50" />
      </button>

      <ActiveProjectDialog open={open} onOpenChange={setOpen} />
    </>
  );
};

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const ActiveProjectDialog: FC<DialogProps> = ({ open, onOpenChange }) => {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const isSuperuser = useIsAdmin();
  const { data } = useProjects();
  const currentProject = useProjectStore((s) => s.currentProject);
  const setProject = useProjectStore((s) => s.setProject);
  const clearProject = useProjectStore((s) => s.clearProject);

  const projects = data?.items ?? [];
  const update = useUpdateProject(currentProject?.id ?? '');

  const schema = z.object({
    name: z.string().trim().min(1, t('errors.required')),
    code: z
      .string()
      .trim()
      .min(1, t('errors.required'))
      .regex(/^[a-z0-9-]+$/, t('projects.code_format')),
    description: z.string().trim().optional(),
  });
  type FormValues = z.infer<typeof schema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', code: '', description: '' },
  });

  // Refill when the dialog opens or the selection changes underneath it, so the
  // form always describes the project the switcher above it is pointing at.
  const { reset } = form;
  useEffect(() => {
    reset({
      name: currentProject?.name ?? '',
      code: currentProject?.code ?? '',
      description: currentProject?.description ?? '',
    });
  }, [currentProject, open, reset]);

  const handleSwitch = (value: string) => {
    if (value === ALL_PROJECTS) {
      clearProject();
    } else {
      const next = projects.find((p) => p.id === value);
      if (!next) return;
      setProject(next);
      toast.success(t('projects.selected', { name: next.name }));
    }
    // Everything else is project-scoped: the cookie the requests carry just
    // changed, so cached data belongs to the previous project.
    void qc.invalidateQueries();
  };

  const onSubmit = async (values: FormValues) => {
    if (!currentProject) return;
    const updated = await update.mutateAsync({
      name: values.name,
      code: values.code,
      description: values.description || undefined,
    });
    setProject(updated);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('projects.active_project')}</DialogTitle>
          <DialogDescription>{t('projects.subtitle')}</DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label>{t('projects.switch_label')}</Label>
          <Select value={currentProject?.id ?? ALL_PROJECTS} onValueChange={handleSwitch}>
            <SelectTrigger>
              <SelectValue placeholder={t('nav.select_project')} />
            </SelectTrigger>
            <SelectContent>
              {isSuperuser && (
                <SelectItem value={ALL_PROJECTS}>{t('projects.all_projects')}</SelectItem>
              )}
              {projects.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {isSuperuser && !currentProject && (
            <p className="text-xs text-muted-foreground">{t('projects.all_projects_hint')}</p>
          )}
        </div>

        {currentProject && (
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 border-t pt-4">
              <p className="text-sm font-medium">{t('projects.detail_title')}</p>
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('projects.name')}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="code"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('projects.code')}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('projects.description')}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <DialogFooter className="pt-2">
                <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                  {t('common.cancel')}
                </Button>
                <Button type="submit" disabled={update.isPending}>
                  {t('common.save')}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        )}
      </DialogContent>
    </Dialog>
  );
};
