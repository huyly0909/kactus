import { type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { setLanguage } from '@/i18n';
import {
  useThemeStore,
  type ThemeMode,
  type ThemeColor,
  type ThemeRadius,
  type ThemeScale,
} from '@/store/themeStore';

// Representative dot color per accent preset (mirrors the `.theme-*` primary /
// chrome in index.css) — just for the picker swatch, not the live token.
const COLOR_DOTS: Record<ThemeColor, string> = {
  default: '#6366f1',
  zinc: '#a1a1aa',
  blue: '#3b82f6',
  emerald: '#10b981',
  violet: '#8b5cf6',
  orange: '#f97316',
  navy: '#1e3a8a',
  plum: '#6b21a8',
  copper: '#b45309',
};

const MODES: ThemeMode[] = ['light', 'dark'];
const COLORS: ThemeColor[] = [
  'default',
  'zinc',
  'blue',
  'emerald',
  'violet',
  'orange',
  'navy',
  'plum',
  'copper',
];
const RADII: ThemeRadius[] = ['sharp', 'classic', 'smooth'];
const SCALES: ThemeScale[] = ['compact', 'normal', 'large', 'xl'];

interface OptionRowProps {
  label: string;
  children: React.ReactNode;
}

const OptionRow: FC<OptionRowProps> = ({ label, children }) => (
  <div className="flex flex-col gap-2">
    <span className="text-sm font-medium text-foreground">{label}</span>
    <div className="flex flex-wrap gap-2">{children}</div>
  </div>
);

interface PillProps {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

const Pill: FC<PillProps> = ({ selected, onClick, children }) => (
  <button
    type="button"
    onClick={onClick}
    aria-pressed={selected}
    className={cn(
      'inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors',
      selected
        ? 'border-primary bg-primary/10 text-primary font-medium'
        : 'border-input text-muted-foreground hover:bg-accent hover:text-accent-foreground',
    )}
  >
    {children}
  </button>
);

export const AppearancePane: FC = () => {
  const { t, i18n } = useTranslation();
  const { mode, color, radius, scale, setMode, setColor, setRadius, setScale } = useThemeStore();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t('settings.appearance')}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <OptionRow label={t('settings.theme.mode')}>
          {MODES.map((m) => (
            <Pill key={m} selected={mode === m} onClick={() => setMode(m)}>
              {t(`settings.theme.mode_${m}`)}
            </Pill>
          ))}
        </OptionRow>

        <OptionRow label={t('settings.theme.color')}>
          {COLORS.map((c) => (
            <Pill key={c} selected={color === c} onClick={() => setColor(c)}>
              <span
                className="h-3 w-3 rounded-full ring-1 ring-black/10"
                style={{ backgroundColor: COLOR_DOTS[c] }}
                aria-hidden
              />
              {t(`settings.theme.color_${c}`)}
            </Pill>
          ))}
        </OptionRow>

        <OptionRow label={t('settings.theme.radius')}>
          {RADII.map((r) => (
            <Pill key={r} selected={radius === r} onClick={() => setRadius(r)}>
              {t(`settings.theme.radius_${r}`)}
            </Pill>
          ))}
        </OptionRow>

        <OptionRow label={t('settings.theme.scale')}>
          {SCALES.map((s) => (
            <Pill key={s} selected={scale === s} onClick={() => setScale(s)}>
              {t(`settings.theme.scale_${s}`)}
            </Pill>
          ))}
        </OptionRow>

        <OptionRow label={t('settings.language')}>
          {(['vi', 'en'] as const).map((lng) => (
            <Pill key={lng} selected={i18n.language === lng} onClick={() => void setLanguage(lng)}>
              {i18n.language === lng && <Check className="h-3.5 w-3.5" />}
              {lng.toUpperCase()}
            </Pill>
          ))}
        </OptionRow>
      </CardContent>
    </Card>
  );
};
