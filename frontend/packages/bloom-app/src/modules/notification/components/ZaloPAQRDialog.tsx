import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { notificationService } from '@/services/notificationService';
import { useCreateZaloChannel, useReauthZaloChannel } from '@/hooks/useNotificationQuery';
import { ZaloRecipientPicker } from './ZaloRecipientPicker';
import type { ZaloRecipient } from '@/types/notification';

type Step = 'loading' | 'scan' | 'confirm' | 'account' | 'pick' | 'error';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 'create' → pick a recipient + create channel. 'reauth' → refresh creds only. */
  mode: 'create' | 'reauth';
  channelName?: string; // create mode
  channelId?: string; // reauth mode
  onDone?: () => void;
}

/**
 * Zalo PA QR login dialog — mirrors the reorc flow:
 *   generate → long-poll scan (swap image on `refreshed`) → long-poll confirm
 *   → complete → (create) pick recipient + create channel / (reauth) refresh creds.
 * ⚠️ Unofficial Zalo API — the user's own account logs in by scanning the QR.
 */
export function ZaloPAQRDialog({
  open,
  onOpenChange,
  mode,
  channelName,
  channelId,
  onDone,
}: Props) {
  const { t } = useTranslation();
  const createChannel = useCreateZaloChannel();
  const reauth = useReauthZaloChannel();

  const [step, setStep] = useState<Step>('loading');
  const [imageUrl, setImageUrl] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [accountName, setAccountName] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const cancelled = useRef(false);

  useEffect(() => {
    if (!open) return;
    cancelled.current = false;
    void runFlow();
    return () => {
      cancelled.current = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const fail = (msg: string) => {
    if (cancelled.current) return;
    setErrorMsg(msg);
    setStep('error');
  };

  async function runFlow() {
    try {
      setStep('loading');
      const qr = await notificationService.zaloPa.generateQR();
      if (cancelled.current) return;
      setSessionId(qr.session_id);
      setImageUrl(qr.image_url);
      setStep('scan');

      // Poll scan (server long-polls ~60s; `refreshed` swaps the QR image).
      for (;;) {
        const scan = await notificationService.zaloPa.waitForScan(qr.session_id);
        if (cancelled.current) return;
        if (scan.status === 'scanned') break;
        if (scan.status === 'refreshed') {
          if (scan.image_url) setImageUrl(scan.image_url);
          continue;
        }
        return fail(t('notification.zalo.qr_expired'));
      }
      setStep('confirm');

      // Poll confirm.
      const confirm = await notificationService.zaloPa.waitForConfirm(qr.session_id);
      if (cancelled.current) return;
      if (confirm.status !== 'confirmed') return fail(t('notification.zalo.qr_rejected'));

      // Finalize login.
      const done = await notificationService.zaloPa.completeLogin(qr.session_id);
      if (cancelled.current) return;
      setAccountName(done.account_name ?? '');

      if (mode === 'reauth') {
        if (!channelId) return fail(t('common.error_generic'));
        await reauth.mutateAsync({ channelId, sessionId: qr.session_id });
        finish();
        return;
      }
      setStep('pick');
    } catch {
      fail(t('notification.zalo.qr_failed'));
    }
  }

  const finish = () => {
    onDone?.();
    onOpenChange(false);
  };

  const handlePick = async (recipient: ZaloRecipient) => {
    await createChannel.mutateAsync({
      session_id: sessionId,
      name: channelName || recipient.name,
      thread_id: recipient.id,
      thread_type: recipient.is_group ? 1 : 0,
      recipient_name: recipient.name,
    });
    finish();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('notification.zalo.login_title')}</DialogTitle>
        </DialogHeader>

        <div className="mb-3 flex items-start gap-2 rounded-md bg-warning/10 p-2 text-xs text-muted-foreground">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--warning)]" />
          <span>{t('notification.zalo.unofficial_warning')}</span>
        </div>

        {step === 'loading' && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        )}

        {step === 'scan' && (
          <div className="flex flex-col items-center gap-3 py-2">
            {imageUrl && (
              <img
                src={imageUrl}
                alt="Zalo QR"
                className="h-56 w-56 rounded-md border border-border"
              />
            )}
            <p className="text-center text-sm text-muted-foreground">
              {t('notification.zalo.scan_hint')}
            </p>
          </div>
        )}

        {step === 'confirm' && (
          <div className="flex flex-col items-center gap-3 py-10">
            <RefreshCw className="h-6 w-6 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">{t('notification.zalo.confirm_hint')}</p>
          </div>
        )}

        {step === 'pick' && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-[var(--gain)]">
              <CheckCircle2 className="h-4 w-4" />
              <span>{t('notification.zalo.logged_in_as', { name: accountName })}</span>
            </div>
            <p className="text-sm text-muted-foreground">{t('notification.zalo.pick_hint')}</p>
            <ZaloRecipientPicker
              sessionId={sessionId}
              onPick={handlePick}
              disabled={createChannel.isPending}
            />
          </div>
        )}

        {step === 'error' && (
          <div className="flex flex-col items-center gap-3 py-8">
            <AlertTriangle className="h-8 w-8 text-[var(--loss)]" />
            <p className="text-center text-sm text-muted-foreground">{errorMsg}</p>
            <Button variant="outline" onClick={() => void runFlow()}>
              <RefreshCw className="mr-1 h-4 w-4" />
              {t('notification.zalo.retry')}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
