import { useMemo } from 'react';
import { Users, Loader2, Square, CheckSquare } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { matchesSearch } from '@/lib/text';
import type { ZaloRecipient } from '@/types/notification';

/** Stable selection key — user and group id spaces may overlap. */
export function zaloRecipientKey(r: Pick<ZaloRecipient, 'id' | 'is_group'>): string {
  return `${r.is_group ? 'g' : 'u'}-${r.id}`;
}

interface Props {
  /** The account's whole directory — session (create) or stored creds (edit). */
  recipients: ZaloRecipient[] | undefined;
  isLoading: boolean;
  query: string;
  onQueryChange: (query: string) => void;
  /** Selection lives in the parent so it survives searching. */
  selected: Map<string, ZaloRecipient>;
  onToggle: (recipient: ZaloRecipient) => void;
  disabled?: boolean;
}

/** Searchable multi-select over a Zalo account's friends + groups.
 *
 * Filtering is **local**: the directory is fetched once (three sequential
 * round-trips to Zalo), so searching it server-side made every keystroke a
 * multi-second refetch that blanked the list. `matchesSearch` also folds
 * diacritics, so "duc" finds "Thành Đức".
 */
export function ZaloConversationPicker({
  recipients,
  isLoading,
  query,
  onQueryChange,
  selected,
  onToggle,
  disabled,
}: Props) {
  const { t } = useTranslation();
  const visible = useMemo(
    () => (recipients ?? []).filter((r) => matchesSearch(r.name, query)),
    [recipients, query],
  );

  return (
    <div className="space-y-3">
      <Input
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder={t('notification.zalo.search_recipient')}
        autoFocus
      />
      <div className="max-h-96 space-y-1 overflow-y-auto rounded-md border border-border p-1">
        {isLoading && (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        )}
        {!isLoading && visible.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">{t('common.no_results')}</p>
        )}
        {!isLoading &&
          visible.map((r) => {
            const isSelected = selected.has(zaloRecipientKey(r));
            return (
              <button
                key={zaloRecipientKey(r)}
                type="button"
                disabled={disabled}
                onClick={() => onToggle(r)}
                aria-pressed={isSelected}
                className={cn(
                  'flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-accent disabled:opacity-50',
                  isSelected && 'bg-accent/60',
                )}
              >
                {isSelected ? (
                  <CheckSquare className="h-4 w-4 shrink-0 text-primary" />
                ) : (
                  <Square className="h-4 w-4 shrink-0 text-muted-foreground" />
                )}
                <Avatar size="sm">
                  {r.avatar && <AvatarImage src={r.avatar} alt="" />}
                  <AvatarFallback>{r.name.charAt(0).toUpperCase()}</AvatarFallback>
                </Avatar>
                <span className="flex-1 truncate">{r.name}</span>
                {r.is_group && (
                  <Badge variant="secondary">
                    <Users className="mr-1 h-3 w-3" />
                    {t('notification.zalo.group')}
                  </Badge>
                )}
              </button>
            );
          })}
      </div>
      <p className="text-xs text-muted-foreground">
        {t('notification.zalo.selected_count', { count: selected.size })}
      </p>
    </div>
  );
}
