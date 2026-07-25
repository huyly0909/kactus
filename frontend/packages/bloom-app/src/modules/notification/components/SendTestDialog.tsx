import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useSendChannel } from '@/hooks/useNotificationQuery';
import type { NotificationLevel } from '@/types/notification';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  channelId: string;
}

const LEVELS: NotificationLevel[] = ['info', 'warning', 'critical'];

/** Compose + send a one-off notification event to a channel. */
export function SendTestDialog({ open, onOpenChange, channelId }: Props) {
  const { t } = useTranslation();
  const send = useSendChannel(channelId);

  const schema = z.object({
    title: z.string().trim().min(1, t('errors.required')),
    body: z.string().trim().optional(),
    level: z.enum(['info', 'warning', 'critical']),
  });
  type FormValues = z.infer<typeof schema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: '', body: '', level: 'info' },
  });

  const handleOpenChange = (o: boolean) => {
    if (!o) form.reset();
    onOpenChange(o);
  };

  const onSubmit = async (values: FormValues) => {
    await send.mutateAsync({
      title: values.title,
      body: values.body || undefined,
      level: values.level,
    });
    form.reset();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('notification.send_title')}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('notification.event_title')}</FormLabel>
                  <FormControl>
                    <Input autoFocus {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="body"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('notification.event_body')}</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="level"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('notification.level')}</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {LEVELS.map((lv) => (
                        <SelectItem key={lv} value={lv}>
                          {t(`notification.level_${lv}`)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormItem>
              )}
            />
            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
                {t('common.cancel')}
              </Button>
              <Button type="submit" disabled={send.isPending}>
                {t('notification.send')}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
