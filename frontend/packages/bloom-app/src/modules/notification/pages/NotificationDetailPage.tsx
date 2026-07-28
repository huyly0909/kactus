import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Send, FlaskConical, Trash2, Save, Users, Pencil, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  useNotificationChannel,
  useUpdateChannel,
  useDeleteChannel,
  useTestChannel,
  useZaloTestMessage,
} from '@/hooks/useNotificationQuery';
import { ChannelLogTable } from '@modules/notification/components/ChannelLogTable';
import { SendTestDialog } from '@modules/notification/components/SendTestDialog';
import { ZaloRecipientsEditDialog } from '@modules/notification/components/ZaloRecipientsEditDialog';
import type { ZaloPAConfig, ZaloRecipientTarget } from '@/types/notification';

/** Saved conversations of a zalo_pa config, tolerating the legacy single shape. */
function zaloTargets(config: ZaloPAConfig): ZaloRecipientTarget[] {
  if (config.recipients?.length) return config.recipients;
  if (config.thread_id) {
    return [
      {
        thread_id: config.thread_id,
        thread_type: config.thread_type ?? 0,
        name: config.recipient_name,
      },
    ];
  }
  return [];
}

export function NotificationDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id = '' } = useParams<{ id: string }>();
  const { data: channel, isLoading } = useNotificationChannel(id);
  const update = useUpdateChannel(id);
  const remove = useDeleteChannel();
  const test = useTestChannel();
  const zaloTest = useZaloTestMessage();

  const [name, setName] = useState('');
  const [sendOpen, setSendOpen] = useState(false);
  const [editRecipientsOpen, setEditRecipientsOpen] = useState(false);
  const nameValue = name || channel?.name || '';

  if (isLoading || !channel) {
    return (
      <div className="p-6 md:p-8">
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const handleSave = async () => {
    if (nameValue.trim() && nameValue !== channel.name) {
      await update.mutateAsync({ name: nameValue.trim() });
    }
  };

  const handleDelete = async () => {
    await remove.mutateAsync(id);
    navigate('/notifications');
  };

  const isZalo = channel.channel_type === 'zalo_pa';
  const targets = isZalo ? zaloTargets(channel.config as ZaloPAConfig) : [];

  return (
    <div className="p-6 md:p-8">
      <button
        onClick={() => navigate('/notifications')}
        className="mb-4 flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t('common.back')}
      </button>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight">{channel.name}</h1>
          <Badge variant="secondary">{t(`notification.type_${channel.channel_type}`)}</Badge>
          <Badge variant={channel.is_active ? 'success' : 'secondary'}>
            {channel.is_active ? t('common.active') : t('common.inactive')}
          </Badge>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => test.mutate(id)} disabled={test.isPending}>
            <FlaskConical className="mr-1 h-4 w-4" />
            {t('notification.test')}
          </Button>
          {isZalo && (
            <Button
              variant="outline"
              onClick={() => zaloTest.mutate(id)}
              disabled={zaloTest.isPending || !channel.is_active}
              title={t('notification.zalo.test_message')}
            >
              <Zap className="mr-1 h-4 w-4" />
              {t('notification.zalo.test_message')}
            </Button>
          )}
          <Button onClick={() => setSendOpen(true)}>
            <Send className="mr-1 h-4 w-4" />
            {t('notification.send')}
          </Button>
        </div>
      </div>

      {/* 1:3, not 1:2 — settings is three fields, while the history table now
          carries six columns and would otherwise scroll sideways. */}
      <div className="grid gap-6 lg:grid-cols-4">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">{t('notification.settings')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ch-name">{t('notification.name')}</Label>
              <Input id="ch-name" value={nameValue} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="flex items-center justify-between">
              <Label>{t('common.active')}</Label>
              <Button
                variant="outline"
                size="sm"
                onClick={() => update.mutate({ is_active: !channel.is_active })}
              >
                {channel.is_active ? t('notification.deactivate') : t('notification.activate')}
              </Button>
            </div>
            {isZalo && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>{t('notification.zalo.conversations')}</Label>
                  <Button variant="outline" size="sm" onClick={() => setEditRecipientsOpen(true)}>
                    <Pencil className="mr-1 h-3.5 w-3.5" />
                    {t('common.edit')}
                  </Button>
                </div>
                {targets.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t('notification.zalo.no_conversations')}
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {targets.map((r) => (
                      <span
                        key={`${r.thread_type}-${r.thread_id}`}
                        className="inline-flex items-center gap-1.5 rounded-full border border-border py-0.5 pl-0.5 pr-2.5 text-xs"
                      >
                        <Avatar size="sm" className="size-5">
                          {r.avatar && <AvatarImage src={r.avatar} alt="" />}
                          <AvatarFallback className="text-[10px]">
                            {(r.name || r.thread_id).charAt(0).toUpperCase()}
                          </AvatarFallback>
                        </Avatar>
                        <span className="max-w-40 truncate">{r.name || r.thread_id}</span>
                        {r.thread_type === 1 && <Users className="h-3 w-3 text-muted-foreground" />}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
            <div className="flex justify-between pt-2">
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={handleDelete}
              >
                <Trash2 className="mr-1 h-4 w-4" />
                {t('common.delete')}
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={update.isPending || nameValue === channel.name}
              >
                <Save className="mr-1 h-4 w-4" />
                {t('common.save')}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle className="text-base">{t('notification.history')}</CardTitle>
          </CardHeader>
          <CardContent>
            <ChannelLogTable channelId={id} />
          </CardContent>
        </Card>
      </div>

      <SendTestDialog open={sendOpen} onOpenChange={setSendOpen} channelId={id} />
      {isZalo && (
        <ZaloRecipientsEditDialog
          open={editRecipientsOpen}
          onOpenChange={setEditRecipientsOpen}
          channel={channel}
        />
      )}
    </div>
  );
}
