import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Users, User, Loader2 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useZaloRecipients } from '@/hooks/useNotificationQuery';
import type { ZaloRecipient } from '@/types/notification';

interface Props {
  sessionId: string;
  onPick: (recipient: ZaloRecipient) => void;
  disabled?: boolean;
}

/** Searchable friends + groups list of a completed Zalo login session. */
export function ZaloRecipientPicker({ sessionId, onPick, disabled }: Props) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const { data: recipients, isLoading } = useZaloRecipients(sessionId, query);

  return (
    <div className="space-y-3">
      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t('notification.zalo.search_recipient')}
        autoFocus
      />
      <div className="max-h-72 space-y-1 overflow-y-auto rounded-md border border-border p-1">
        {isLoading && (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        )}
        {!isLoading && (recipients?.length ?? 0) === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">{t('common.no_results')}</p>
        )}
        {recipients?.map((r) => (
          <button
            key={`${r.is_group ? 'g' : 'u'}-${r.id}`}
            type="button"
            disabled={disabled}
            onClick={() => onPick(r)}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-accent disabled:opacity-50"
          >
            {r.is_group ? (
              <Users className="h-4 w-4 shrink-0 text-muted-foreground" />
            ) : (
              <User className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}
            <span className="flex-1 truncate">{r.name}</span>
            {r.is_group && <Badge variant="secondary">{t('notification.zalo.group')}</Badge>}
          </button>
        ))}
      </div>
    </div>
  );
}
