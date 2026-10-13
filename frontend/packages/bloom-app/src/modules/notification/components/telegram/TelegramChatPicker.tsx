import { useMemo } from 'react';
import { Loader2, Hash, Users, User, Megaphone } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { matchesSearch } from '@/lib/text';
import type { TelegramChat } from '@/types/notification';

const TYPE_ICON: Record<string, React.ElementType> = {
  channel: Megaphone,
  supergroup: Users,
  group: Users,
  private: User,
};

interface Props {
  chats: TelegramChat[] | undefined;
  isLoading: boolean;
  query: string;
  onQueryChange: (query: string) => void;
  /** Single select — a Telegram channel config holds exactly one `chat_id`. */
  selectedId: string;
  onSelect: (chat: TelegramChat) => void;
  disabled?: boolean;
}

/** Searchable single-select over the chats a bot can see.
 *
 * Filtering is local: discovery is one `getUpdates` round-trip that returns the
 * whole (small) set, so re-querying per keystroke would only add latency.
 * `matchesSearch` folds diacritics, so "vang" finds "Giá Vàng".
 */
export function TelegramChatPicker({
  chats,
  isLoading,
  query,
  onQueryChange,
  selectedId,
  onSelect,
  disabled,
}: Props) {
  const { t } = useTranslation();
  const visible = useMemo(
    () => (chats ?? []).filter((c) => matchesSearch(`${c.title} ${c.username ?? ''}`, query)),
    [chats, query],
  );

  return (
    <div className="space-y-3">
      <Input
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder={t('notification.telegram.search_chat')}
        autoFocus
      />
      <div className="max-h-80 space-y-1 overflow-y-auto rounded-md border border-border p-1">
        {isLoading && (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        )}
        {!isLoading && visible.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">{t('common.no_results')}</p>
        )}
        {!isLoading &&
          visible.map((chat) => {
            const Icon = TYPE_ICON[chat.type] ?? Hash;
            const isSelected = chat.id === selectedId;
            return (
              <button
                key={chat.id}
                type="button"
                disabled={disabled}
                onClick={() => onSelect(chat)}
                aria-pressed={isSelected}
                className={cn(
                  'flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-accent disabled:opacity-50',
                  isSelected && 'bg-accent/60',
                )}
              >
                <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{chat.title}</span>
                  {/* The id is the thing being chosen — show it, don't hide it. */}
                  <span className="block truncate font-mono text-xs text-muted-foreground">
                    {chat.id}
                    {chat.username ? ` · @${chat.username}` : ''}
                  </span>
                </span>
                <Badge variant="secondary">{chat.type}</Badge>
              </button>
            );
          })}
      </div>
    </div>
  );
}
