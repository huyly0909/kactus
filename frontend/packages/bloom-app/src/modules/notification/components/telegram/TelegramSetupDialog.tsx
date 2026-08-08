import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, AlertTriangle, CheckCircle2, RefreshCw, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  useCreateChannel,
  useTelegramChannelChats,
  useTelegramDiscoverChats,
  useTelegramReauth,
  useTelegramResolveChat,
  useTelegramUpdateChat,
  useTelegramVerify,
} from '@/hooks/useNotificationQuery';
import { TelegramChatPicker } from './TelegramChatPicker';
import type { TelegramChat } from '@/types/notification';

type Step = 'token' | 'pick' | 'error';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 'create'    → verify token, pick a chat, create the channel.
   *  'edit-chat' → repoint an existing channel using its stored token.
   *  'reauth'    → replace the bot token, keeping the chat. */
  mode: 'create' | 'edit-chat' | 'reauth';
  channelName?: string; // create mode
  channelId?: string; // edit-chat mode
  onDone?: () => void;
}

/**
 * Telegram setup wizard.
 *
 * Telegram never shows a channel's numeric id, so the middle of this flow is the
 * only way most users can configure a channel: add the bot as an administrator,
 * post once, and the bot's `getUpdates` reveals the `-100…` id.
 *
 * In 'edit-chat' mode the token is never in play — the server reads the stored
 * one, so the dialog opens straight on the picker.
 */
export function TelegramSetupDialog({
  open,
  onOpenChange,
  mode,
  channelName,
  channelId,
  onDone,
}: Props) {
  const { t } = useTranslation();
  const verify = useTelegramVerify();
  const discover = useTelegramDiscoverChats();
  const resolve = useTelegramResolveChat();
  const createChannel = useCreateChannel();
  const updateChat = useTelegramUpdateChat(channelId ?? '');
  const reauth = useTelegramReauth(channelId ?? '');

  const [step, setStep] = useState<Step>(mode === 'edit-chat' ? 'pick' : 'token');
  const [botToken, setBotToken] = useState('');
  const [botUsername, setBotUsername] = useState('');
  const [chats, setChats] = useState<TelegramChat[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [manualId, setManualId] = useState('');
  const [query, setQuery] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const cancelled = useRef(false);

  // edit-chat sources the list from the channel's stored token instead.
  const storedChats = useTelegramChannelChats(channelId ?? '', mode === 'edit-chat' && open);

  useEffect(() => {
    if (!open) return;
    cancelled.current = false;
    setStep(mode === 'edit-chat' ? 'pick' : 'token');
    setBotToken('');
    setBotUsername('');
    setChats([]);
    setSelectedId('');
    setManualId('');
    setQuery('');
    setErrorMsg('');
    return () => {
      cancelled.current = true;
    };
  }, [open, mode]);

  const fail = (msg: string) => {
    if (cancelled.current) return;
    setErrorMsg(msg);
    setStep('error');
  };

  /** Step 1 → 2: prove the token works, then look for chats.
   *  In 'reauth' there is nothing to pick — the chat is already saved. */
  async function verifyAndDiscover() {
    const token = botToken.trim();
    if (!token) return;
    try {
      const bot = await verify.mutateAsync(token);
      if (cancelled.current) return;
      setBotUsername(bot.username);
      if (mode === 'reauth') {
        // The server re-verifies before storing, so a dead token can never
        // replace a working one even if this check were skipped.
        await reauth.mutateAsync(token);
        finish();
        return;
      }
      // An empty list here is expected, not an error — the picker explains it.
      const found = await discover.mutateAsync(token);
      if (cancelled.current) return;
      setChats(found);
      setStep('pick');
    } catch (err) {
      fail(errorText(err));
    }
  }

  /** Re-run discovery after the user adds the bot as admin and posts. */
  async function refreshChats() {
    try {
      if (mode === 'edit-chat') {
        await storedChats.refetch();
        return;
      }
      const found = await discover.mutateAsync(botToken.trim());
      if (!cancelled.current) setChats(found);
    } catch (err) {
      fail(errorText(err));
    }
  }

  /** The `@public_channel` path, and the escape hatch when the list is empty. */
  async function resolveManual() {
    const typed = manualId.trim();
    if (!typed) return;
    if (mode === 'edit-chat') {
      // No token available client-side; accept the id as typed.
      setSelectedId(typed);
      return;
    }
    try {
      const chat = await resolve.mutateAsync({ botToken: botToken.trim(), chatId: typed });
      if (cancelled.current) return;
      setChats((prev) => [chat, ...prev.filter((c) => c.id !== chat.id)]);
      setSelectedId(chat.id);
      setManualId('');
    } catch {
      /* toast already fired in the hook */
    }
  }

  const finish = () => {
    onDone?.();
    onOpenChange(false);
  };

  const handleConfirm = async () => {
    if (!selectedId) return;
    if (mode === 'edit-chat') {
      await updateChat.mutateAsync(selectedId);
    } else {
      const picked = chats.find((c) => c.id === selectedId);
      await createChannel.mutateAsync({
        name: channelName?.trim() || picked?.title || selectedId,
        channel_type: 'telegram',
        config: { bot_token: botToken.trim(), chat_id: selectedId },
      });
    }
    finish();
  };

  const visibleChats = mode === 'edit-chat' ? storedChats.data : chats;
  const listLoading = mode === 'edit-chat' ? storedChats.isFetching : discover.isPending;
  const busy = createChannel.isPending || updateChat.isPending;
  const verifying = verify.isPending || discover.isPending || reauth.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* Wider than max-w-md: rows carry a title, a -100… id and a type badge. */}
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {mode === 'create' && t('notification.telegram.setup_title')}
            {mode === 'edit-chat' && t('notification.telegram.change_chat')}
            {mode === 'reauth' && t('notification.telegram.reconnect')}
          </DialogTitle>
        </DialogHeader>

        {step === 'token' && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="tg-token">{t('notification.telegram.bot_token')}</Label>
              <Input
                id="tg-token"
                value={botToken}
                onChange={(e) => setBotToken(e.target.value)}
                placeholder="123456789:AAF…"
                autoComplete="off"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void verifyAndDiscover();
                }}
              />
              <p className="text-xs text-muted-foreground">
                {mode === 'reauth'
                  ? t('notification.telegram.reauth_hint')
                  : t('notification.telegram.token_hint')}
              </p>
            </div>
            <div className="flex justify-end">
              <Button
                onClick={() => void verifyAndDiscover()}
                disabled={!botToken.trim() || verifying}
              >
                {verifying && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                {mode === 'reauth'
                  ? t('notification.telegram.reconnect')
                  : t('notification.telegram.verify')}
              </Button>
            </div>
          </div>
        )}

        {step === 'pick' && (
          <div className="space-y-3">
            {botUsername && (
              <div className="flex items-center gap-2 text-sm text-[var(--gain)]">
                <CheckCircle2 className="h-4 w-4" />
                <span>{t('notification.telegram.bot_verified', { name: botUsername })}</span>
              </div>
            )}

            <TelegramChatPicker
              chats={visibleChats}
              isLoading={listLoading}
              query={query}
              onQueryChange={setQuery}
              selectedId={selectedId}
              onSelect={(chat) => setSelectedId(chat.id)}
              disabled={busy}
            />

            {/* The common first run: the bot is admin but nothing was posted yet,
                so Telegram has queued no update naming the channel. */}
            {!listLoading && (visibleChats?.length ?? 0) === 0 && (
              <div className="flex items-start gap-2 rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{t('notification.telegram.no_chats_hint')}</span>
              </div>
            )}

            <div className="flex flex-wrap items-end gap-2">
              <div className="min-w-48 flex-1 space-y-1.5">
                <Label htmlFor="tg-manual">{t('notification.telegram.manual_chat_id')}</Label>
                <Input
                  id="tg-manual"
                  value={manualId}
                  onChange={(e) => setManualId(e.target.value)}
                  placeholder="-1001234567890 / @my_channel"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void resolveManual();
                  }}
                />
              </div>
              <Button
                variant="outline"
                onClick={() => void resolveManual()}
                disabled={!manualId.trim() || resolve.isPending}
              >
                {resolve.isPending ? (
                  <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                ) : (
                  <Search className="mr-1 h-4 w-4" />
                )}
                {t('notification.telegram.use_id')}
              </Button>
            </div>

            <div className="flex justify-between gap-2">
              <Button variant="outline" onClick={() => void refreshChats()} disabled={listLoading}>
                <RefreshCw className={`mr-1 h-4 w-4 ${listLoading ? 'animate-spin' : ''}`} />
                {t('notification.telegram.find_chats')}
              </Button>
              <Button onClick={() => void handleConfirm()} disabled={!selectedId || busy}>
                {busy && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                {mode === 'create' ? t('common.create') : t('common.save')}
              </Button>
            </div>
          </div>
        )}

        {step === 'error' && (
          <div className="flex flex-col items-center gap-3 py-8">
            <AlertTriangle className="h-8 w-8 text-[var(--loss)]" />
            <p className="text-center text-sm text-muted-foreground">{errorMsg}</p>
            <Button
              variant="outline"
              onClick={() => setStep(mode === 'edit-chat' ? 'pick' : 'token')}
            >
              <RefreshCw className="mr-1 h-4 w-4" />
              {t('notification.telegram.back')}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Surface Telegram's own wording (bad token, webhook conflict) — it is the
 * actionable part, and the backend already normalises it into `message`. */
function errorText(err: unknown): string {
  const detail = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
  return detail || (err as Error)?.message || 'Telegram request failed';
}
