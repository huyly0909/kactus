import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Send, Hash, MessageCircle } from 'lucide-react';
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
import { useCreateChannel } from '@/hooks/useNotificationQuery';
import type { NotificationChannelType } from '@/types/notification';
import { ZaloPAQRDialog } from './ZaloPAQRDialog';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const TYPES: { value: NotificationChannelType; labelKey: string; icon: React.ElementType }[] = [
  { value: 'telegram', labelKey: 'notification.type_telegram', icon: Send },
  { value: 'slack', labelKey: 'notification.type_slack', icon: Hash },
  { value: 'zalo_pa', labelKey: 'notification.type_zalo_pa', icon: MessageCircle },
];

/** Create-channel modal: Select type → per-type config (Zalo launches QR). */
export function ChannelFormDialog({ open, onOpenChange }: Props) {
  const { t } = useTranslation();
  const create = useCreateChannel();
  const [qrOpen, setQrOpen] = useState(false);

  const schema = z
    .object({
      name: z.string().trim().min(1, t('errors.required')),
      type: z.enum(['telegram', 'slack', 'zalo_pa']),
      bot_token: z.string().optional().default(''),
      chat_id: z.string().optional().default(''),
      webhook_url: z.string().optional().default(''),
    })
    .superRefine((val, ctx) => {
      if (val.type === 'telegram') {
        if (!val.bot_token.trim())
          ctx.addIssue({ code: 'custom', path: ['bot_token'], message: t('errors.required') });
        if (!val.chat_id.trim())
          ctx.addIssue({ code: 'custom', path: ['chat_id'], message: t('errors.required') });
      }
      if (val.type === 'slack' && !val.webhook_url.trim())
        ctx.addIssue({ code: 'custom', path: ['webhook_url'], message: t('errors.required') });
    });
  type FormValues = z.input<typeof schema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', type: 'telegram', bot_token: '', chat_id: '', webhook_url: '' },
  });

  const type = form.watch('type') as NotificationChannelType;
  const name = form.watch('name') ?? '';

  const handleOpenChange = (o: boolean) => {
    if (!o) form.reset();
    onOpenChange(o);
  };

  const onSubmit = async (values: FormValues) => {
    if (values.type === 'zalo_pa') {
      setQrOpen(true);
      return;
    }
    const config =
      values.type === 'telegram'
        ? { bot_token: values.bot_token ?? '', chat_id: values.chat_id ?? '' }
        : { webhook_url: values.webhook_url ?? '' };
    await create.mutateAsync({ name: values.name.trim(), channel_type: values.type, config });
    form.reset();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('notification.create_title')}</DialogTitle>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('notification.channel_type')}</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {TYPES.map((ty) => {
                        const Icon = ty.icon;
                        return (
                          <SelectItem key={ty.value} value={ty.value}>
                            <span className="flex items-center gap-2">
                              <Icon className="h-4 w-4" />
                              {t(ty.labelKey)}
                            </span>
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('notification.name')}</FormLabel>
                  <FormControl>
                    <Input placeholder={t('notification.name_placeholder')} autoFocus {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {type === 'telegram' && (
              <>
                <FormField
                  control={form.control}
                  name="bot_token"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('notification.telegram.bot_token')}</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="chat_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('notification.telegram.chat_id')}</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </>
            )}

            {type === 'slack' && (
              <FormField
                control={form.control}
                name="webhook_url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('notification.slack.webhook_url')}</FormLabel>
                    <FormControl>
                      <Input placeholder="https://hooks.slack.com/services/..." {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            {type === 'zalo_pa' && (
              <p className="rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
                {t('notification.zalo.create_hint')}
              </p>
            )}

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
                {t('common.cancel')}
              </Button>
              <Button type="submit" disabled={create.isPending}>
                {type === 'zalo_pa' ? t('notification.zalo.connect') : t('common.create')}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>

      <ZaloPAQRDialog
        open={qrOpen}
        onOpenChange={setQrOpen}
        mode="create"
        channelName={name.trim()}
        onDone={() => {
          form.reset();
          onOpenChange(false);
        }}
      />
    </Dialog>
  );
}
