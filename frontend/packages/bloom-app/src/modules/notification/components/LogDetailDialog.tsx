import { type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Users, User, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useFormatDateTime } from '@/hooks/useFormatDateTime';
import type { NotificationLevel, NotificationLog } from '@/types/notification';

interface Props {
  log: NotificationLog | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const LEVEL_VARIANT: Record<NotificationLevel, 'secondary' | 'warning' | 'danger'> = {
  info: 'secondary',
  warning: 'warning',
  critical: 'danger',
};

const Field: FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="space-y-1">
    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
    <div className="text-sm">{children}</div>
  </div>
);

/**
 * Everything one send left behind: the message as sent, which conversations
 * received it (and why the others did not), and each failed transport attempt.
 *
 * All of it already travels on the log row from `GET /{id}/logs`, so opening a
 * row costs no request.
 */
export const LogDetailDialog: FC<Props> = ({ log, open, onOpenChange }) => {
  const { t } = useTranslation();
  const fmtDateTime = useFormatDateTime();
  if (!log) return null;

  const delivered = log.delivered_count ?? log.targets.filter((tg) => tg.ok).length;
  const total = log.target_count ?? log.targets.length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t('notification.log.detail_title')}</DialogTitle>
        </DialogHeader>

        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={log.status === 'success' ? 'success' : 'danger'}>
              {t(`notification.status_${log.status}`)}
            </Badge>
            <Badge variant={LEVEL_VARIANT[log.level]}>{t(`notification.level_${log.level}`)}</Badge>
            <Badge variant="outline">{t(`notification.trigger_${log.trigger}`)}</Badge>
          </div>

          <Field label={t('notification.event_title')}>
            <span className="font-medium">{log.event_title}</span>
          </Field>

          {log.body && (
            <Field label={t('notification.event_body')}>
              <p className="whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-sm">{log.body}</p>
            </Field>
          )}

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Field label={t('notification.log.attempts')}>
              <span className="tabular-nums">{log.attempts}</span>
            </Field>
            <Field label={t('notification.log.time')}>
              <span className="text-xs">{fmtDateTime(log.started_at)}</span>
            </Field>
            <Field label={t('notification.log.finished')}>
              <span className="text-xs">{fmtDateTime(log.finished_at)}</span>
            </Field>
          </div>

          {log.error && (
            <Field label={t('notification.log.error')}>
              <p className="whitespace-pre-wrap text-sm text-[var(--loss)]">{log.error}</p>
            </Field>
          )}

          {log.targets.length > 0 && (
            <Field
              label={`${t('notification.log.recipients')} — ${t('notification.log.delivered', {
                delivered,
                total,
              })}`}
            >
              <ul className="divide-y divide-border rounded-md border border-border">
                {log.targets.map((target) => (
                  <li
                    key={`${target.thread_type}-${target.thread_id}`}
                    className="flex items-start gap-2 px-3 py-2"
                  >
                    {target.ok ? (
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-[var(--gain)]" />
                    ) : (
                      <X className="mt-0.5 h-4 w-4 shrink-0 text-[var(--loss)]" />
                    )}
                    {target.thread_type === 1 ? (
                      <Users className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    ) : (
                      <User className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate">{target.name || target.thread_id}</p>
                      {target.error && <p className="text-xs text-[var(--loss)]">{target.error}</p>}
                    </div>
                  </li>
                ))}
              </ul>
            </Field>
          )}

          {log.attempt_errors.length > 0 && (
            <Field label={t('notification.log.attempt_history')}>
              <ul className="divide-y divide-border rounded-md border border-border">
                {log.attempt_errors.map((attempt) => (
                  <li key={attempt.attempt} className="px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-medium">
                        {t('notification.log.attempt_n', { n: attempt.attempt })}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {fmtDateTime(attempt.at)}
                      </span>
                    </div>
                    <p className="mt-0.5 whitespace-pre-wrap text-xs text-[var(--loss)]">
                      {attempt.error}
                    </p>
                  </li>
                ))}
              </ul>
            </Field>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
