import { type FC, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Moon,
  Sun,
  MonitorSmartphone,
  Palette,
  Box,
  ALargeSmall,
  Globe,
  MapPin,
  Calendar,
  Clock,
  Hash,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { formatDate, formatTime, formatNumber } from '@/lib/locale-format';
import { useAuthStore } from '@/store/authStore';
import { useUpdatePreferences, DEFAULT_TIMEZONE } from '@/hooks/usePreferences';
import {
  useThemeStore,
  type ThemeMode,
  type ThemeColor,
  type ThemeRadius,
  type ThemeScale,
} from '@/store/themeStore';

const MODES: { id: ThemeMode; icon: typeof Sun; labelKey: string }[] = [
  { id: 'light', icon: Sun, labelKey: 'settings.theme.mode_light' },
  { id: 'dark', icon: Moon, labelKey: 'settings.theme.mode_dark' },
];

// jira (the default) leads; two-tone presets render as a split circle so the
// pair reads at a glance. Classes are literal swatches, not the live tokens.
const COLORS: { id: ThemeColor; classes: string[]; labelKey: string }[] = [
  { id: 'jira', classes: ['bg-[#0C66E4]'], labelKey: 'settings.theme.color_jira' },
  { id: 'default', classes: ['bg-indigo-500'], labelKey: 'settings.theme.color_default' },
  { id: 'zinc', classes: ['bg-zinc-500'], labelKey: 'settings.theme.color_zinc' },
  { id: 'blue', classes: ['bg-blue-500'], labelKey: 'settings.theme.color_blue' },
  { id: 'emerald', classes: ['bg-emerald-500'], labelKey: 'settings.theme.color_emerald' },
  { id: 'violet', classes: ['bg-violet-500'], labelKey: 'settings.theme.color_violet' },
  { id: 'orange', classes: ['bg-orange-500'], labelKey: 'settings.theme.color_orange' },
  { id: 'navy', classes: ['bg-blue-950', 'bg-green-700'], labelKey: 'settings.theme.color_navy' },
  {
    id: 'plum',
    classes: ['bg-purple-950', 'bg-orange-600'],
    labelKey: 'settings.theme.color_plum',
  },
  {
    id: 'copper',
    classes: ['bg-orange-800', 'bg-violet-700'],
    labelKey: 'settings.theme.color_copper',
  },
];

// Preview swatches use literal radius classes so the user SEES each preset; the
// applied theme still drives the app via --radius.
const RADII: { id: ThemeRadius; cls: string; labelKey: string }[] = [
  { id: 'sharp', cls: 'rounded-none', labelKey: 'settings.theme.radius_sharp' },
  { id: 'classic', cls: 'rounded-md', labelKey: 'settings.theme.radius_classic' },
  { id: 'smooth', cls: 'rounded-xl', labelKey: 'settings.theme.radius_smooth' },
];

// Preview labels render at their own size — the size IS the preview.
const SCALES: { id: ThemeScale; preview: string; labelKey: string }[] = [
  { id: 'compact', preview: 'text-xs', labelKey: 'settings.theme.scale_compact' },
  { id: 'normal', preview: 'text-sm', labelKey: 'settings.theme.scale_normal' },
  { id: 'large', preview: 'text-base', labelKey: 'settings.theme.scale_large' },
  { id: 'xl', preview: 'text-lg', labelKey: 'settings.theme.scale_xl' },
];

// Curated common zones (a full 400-zone IANA picker would need a searchable
// combobox / new dep — unnecessary here). Offsets are computed at render.
const TIMEZONES = [
  'Asia/Ho_Chi_Minh',
  'Asia/Bangkok',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Asia/Seoul',
  'Asia/Dubai',
  'Asia/Kolkata',
  'UTC',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
  'Australia/Sydney',
];

function tzOffsetLabel(tz: string): string {
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      timeZoneName: 'shortOffset',
    }).formatToParts(new Date());
    return parts.find((p) => p.type === 'timeZoneName')?.value ?? '';
  } catch {
    return '';
  }
}

const OPTION_BASE =
  'flex items-center gap-3 rounded-lg border-2 transition-all outline-none cursor-pointer';
const OPTION_ACTIVE = 'border-primary bg-primary/5 shadow-sm';
const OPTION_INACTIVE = 'border-border/40 hover:border-black/10 dark:hover:border-white/10';

interface SectionProps {
  icon: typeof Sun;
  title: string;
  children: React.ReactNode;
}

const Section: FC<SectionProps> = ({ icon: Icon, title, children }) => (
  <section className="space-y-4">
    <div className="flex items-center gap-2">
      <Icon className="h-5 w-5 text-muted-foreground" />
      <h4 className="text-base font-medium">{title}</h4>
    </div>
    {children}
  </section>
);

export const PreferencesPane: FC = () => {
  const { t, i18n } = useTranslation();
  const { mode, color, radius, scale, setMode, setColor, setRadius, setScale } = useThemeStore();
  const user = useAuthStore((s) => s.user);
  const updatePrefs = useUpdatePreferences();

  const currentLang = i18n.language?.startsWith('en') ? 'en' : 'vi';
  const locale = currentLang === 'en' ? 'en-US' : 'vi-VN';
  const tz = user?.timezone || DEFAULT_TIMEZONE;

  const timezoneOptions = useMemo(
    () => TIMEZONES.map((z) => ({ value: z, label: `${z} (${tzOffsetLabel(z)})` })),
    [],
  );

  const now = useMemo(() => new Date(), []);
  const datePreview = formatDate(now, locale, tz);
  const timePreview = formatTime(now, locale, tz);
  const numberPreview = formatNumber(1234567.89, 2, locale);

  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 p-6 duration-300 md:p-8">
      <div className="mb-8">
        <p className="text-sm text-muted-foreground">{t('settings.preferences_desc')}</p>
      </div>

      <div className="max-w-3xl space-y-10">
        {/* Appearance mode */}
        <Section icon={MonitorSmartphone} title={t('settings.theme.mode')}>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {MODES.map((m) => {
              const Icon = m.icon;
              const active = mode === m.id;
              return (
                <div
                  key={m.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setMode(m.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') setMode(m.id);
                  }}
                  className={cn(
                    OPTION_BASE,
                    'flex-col justify-center p-4',
                    active ? OPTION_ACTIVE : OPTION_INACTIVE,
                  )}
                >
                  <Icon
                    className={cn(
                      'mb-3 h-6 w-6',
                      active ? 'text-primary' : 'text-muted-foreground',
                    )}
                  />
                  <span className="text-sm font-medium">{t(m.labelKey)}</span>
                </div>
              );
            })}
          </div>
        </Section>

        {/* Accent color */}
        <Section icon={Palette} title={t('settings.theme.color')}>
          <div className="flex flex-wrap gap-3">
            {COLORS.map((c) => {
              const active = color === c.id;
              return (
                <div
                  key={c.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setColor(c.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') setColor(c.id);
                  }}
                  className={cn(
                    OPTION_BASE,
                    'px-4 py-2.5',
                    active ? OPTION_ACTIVE : OPTION_INACTIVE,
                  )}
                >
                  <span className="flex h-4 w-4 flex-shrink-0 overflow-hidden rounded-full shadow-inner">
                    {c.classes.map((cls) => (
                      <span key={cls} className={cn('flex-1', cls)} />
                    ))}
                  </span>
                  <span className="text-sm font-medium">{t(c.labelKey)}</span>
                </div>
              );
            })}
          </div>
        </Section>

        {/* Border radius */}
        <Section icon={Box} title={t('settings.theme.radius')}>
          <div className="flex flex-wrap gap-3">
            {RADII.map((r) => {
              const active = radius === r.id;
              return (
                <div
                  key={r.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setRadius(r.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') setRadius(r.id);
                  }}
                  className={cn(
                    'flex w-28 cursor-pointer flex-col items-center gap-2 border-2 bg-background py-4 outline-none transition-all',
                    r.cls,
                    active
                      ? 'border-primary shadow-sm'
                      : 'border-border/40 hover:border-black/10 dark:hover:border-white/10',
                  )}
                >
                  <div className={cn('h-8 w-12 border-2 border-primary/20 bg-primary/10', r.cls)} />
                  <span className="mt-1 text-xs font-semibold">{t(r.labelKey)}</span>
                </div>
              );
            })}
          </div>
        </Section>

        {/* Display size */}
        <Section icon={ALargeSmall} title={t('settings.theme.scale')}>
          <div className="flex flex-wrap gap-3">
            {SCALES.map((s) => {
              const active = scale === s.id;
              return (
                <div
                  key={s.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setScale(s.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') setScale(s.id);
                  }}
                  className={cn(
                    'flex h-16 w-28 cursor-pointer items-center justify-center rounded-lg border-2 bg-background outline-none transition-all',
                    active
                      ? 'border-primary shadow-sm'
                      : 'border-border/40 hover:border-black/10 dark:hover:border-white/10',
                  )}
                >
                  <span
                    className={cn(
                      'font-semibold',
                      s.preview,
                      active ? 'text-primary' : 'text-foreground',
                    )}
                  >
                    {t(s.labelKey)}
                  </span>
                </div>
              );
            })}
          </div>
        </Section>
      </div>

      <div className="my-10 border-t border-border/40" />

      <div className="mb-8">
        <h3 className="text-xl font-semibold tracking-tight">{t('settings.localization')}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t('settings.localization_desc')}</p>
      </div>

      <div className="max-w-3xl space-y-8">
        {/* Language */}
        <section className="grid items-start gap-4 sm:grid-cols-[200px_1fr]">
          <div className="flex items-center gap-2 pt-2">
            <Globe className="h-5 w-5 text-muted-foreground" />
            <h4 className="text-base font-medium">{t('settings.language')}</h4>
          </div>
          <div className="flex max-w-sm gap-1 rounded-lg border border-border/50 bg-muted/50 p-1.5">
            {(['vi', 'en'] as const).map((lng) => {
              const active = currentLang === lng;
              return (
                <Button
                  key={lng}
                  variant={active ? 'default' : 'ghost'}
                  disabled={updatePrefs.isPending}
                  onClick={() => {
                    if (!active) updatePrefs.mutate({ language: lng });
                  }}
                  className={cn('h-9 flex-1', !active && 'text-muted-foreground')}
                >
                  {lng.toUpperCase()}
                </Button>
              );
            })}
          </div>
        </section>

        {/* Timezone */}
        <section className="grid items-start gap-4 sm:grid-cols-[200px_1fr]">
          <div className="flex items-center gap-2 pt-2">
            <MapPin className="h-5 w-5 text-muted-foreground" />
            <h4 className="text-base font-medium">{t('settings.timezone')}</h4>
          </div>
          <div className="max-w-sm">
            <Select
              value={tz}
              disabled={updatePrefs.isPending}
              onValueChange={(v) => {
                if (v !== tz) updatePrefs.mutate({ timezone: v });
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {timezoneOptions.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </section>

        {/* Format preview */}
        <section className="grid items-start gap-4 sm:grid-cols-[200px_1fr]">
          <div className="flex items-center gap-2 pt-2">
            <Calendar className="h-5 w-5 text-muted-foreground" />
            <h4 className="text-base font-medium">{t('settings.formats')}</h4>
          </div>
          <div className="max-w-md overflow-hidden rounded-lg border border-border/50 bg-muted/20">
            <FormatRow
              icon={<Calendar className="h-4 w-4 text-muted-foreground" />}
              label={t('settings.date_format')}
              value={datePreview}
            />
            <FormatRow
              icon={<Clock className="h-4 w-4 text-muted-foreground" />}
              label={t('settings.time_format')}
              value={timePreview}
            />
            <FormatRow
              icon={<Hash className="h-4 w-4 text-muted-foreground" />}
              label={t('settings.number_format')}
              value={numberPreview}
            />
          </div>
        </section>
      </div>
    </div>
  );
};

interface FormatRowProps {
  icon: React.ReactNode;
  label: string;
  value: string;
}

const FormatRow: FC<FormatRowProps> = ({ icon, label, value }) => (
  <div className="flex items-center gap-3 border-b border-border/40 px-4 py-3 last:border-b-0">
    <div className="shrink-0">{icon}</div>
    <div className="w-28 shrink-0 text-sm text-muted-foreground">{label}</div>
    <div className="min-w-0 flex-1 truncate text-sm font-medium tabular-nums">{value}</div>
  </div>
);
