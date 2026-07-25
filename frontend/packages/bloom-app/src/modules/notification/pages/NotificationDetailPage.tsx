import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Send, FlaskConical, Trash2, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useNotificationChannel,
  useUpdateChannel,
  useDeleteChannel,
  useTestChannel,
} from '@/hooks/useNotificationQuery';
import { ChannelLogTable } from '@modules/notification/components/ChannelLogTable';
import { SendTestDialog } from '@modules/notification/components/SendTestDialog';

export function NotificationDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id = '' } = useParams<{ id: string }>();
  const { data: channel, isLoading } = useNotificationChannel(id);
  const update = useUpdateChannel(id);
  const remove = useDeleteChannel();
  const test = useTestChannel();

  const [name, setName] = useState('');
  const [sendOpen, setSendOpen] = useState(false);
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
          <Button onClick={() => setSendOpen(true)}>
            <Send className="mr-1 h-4 w-4" />
            {t('notification.send')}
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
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
                {channel.is_active ? t('common.archive') : t('common.unarchive')}
              </Button>
            </div>
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

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">{t('notification.history')}</CardTitle>
          </CardHeader>
          <CardContent>
            <ChannelLogTable channelId={id} />
          </CardContent>
        </Card>
      </div>

      <SendTestDialog open={sendOpen} onOpenChange={setSendOpen} channelId={id} />
    </div>
  );
}
