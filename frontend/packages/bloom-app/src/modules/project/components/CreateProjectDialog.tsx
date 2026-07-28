import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
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
import { useCreateProject } from '@/hooks/useProjectQuery';
import { projectFormSchema, type ProjectFormValues } from '@/lib/project';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Create-project modal — shadcn Dialog + react-hook-form + zod. */
export function CreateProjectDialog({ open, onOpenChange }: Props) {
  const { t } = useTranslation();
  const create = useCreateProject();

  const form = useForm<ProjectFormValues>({
    resolver: zodResolver(projectFormSchema(t)),
    defaultValues: { name: '', code: '', description: '' },
  });

  const handleOpenChange = (o: boolean) => {
    if (!o) form.reset();
    onOpenChange(o);
  };

  const onSubmit = async (values: ProjectFormValues) => {
    await create.mutateAsync({
      name: values.name,
      code: values.code,
      description: values.description || undefined,
    });
    form.reset();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('projects.create_title')}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('projects.name')}</FormLabel>
                  <FormControl>
                    <Input placeholder={t('projects.name_placeholder')} autoFocus {...field} />
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
                    <Input placeholder={t('projects.code_placeholder')} {...field} />
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
              <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
                {t('common.cancel')}
              </Button>
              <Button type="submit" disabled={create.isPending}>
                {t('common.create')}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
