import { type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { User as UserIcon, Mail, Shield, CheckCircle2, AtSign } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';

interface FieldProps {
  icon: typeof UserIcon;
  label: string;
  value: string;
}

const Field: FC<FieldProps> = ({ icon: Icon, label, value }) => (
  <div className="grid gap-2">
    <label className="flex items-center gap-2 text-sm font-semibold">
      <Icon className="h-4 w-4 text-muted-foreground" />
      {label}
    </label>
    <div className="rounded-lg border border-border/50 bg-muted/50 px-4 py-2.5 text-sm font-medium">
      {value || '—'}
    </div>
  </div>
);

export const ProfilePane: FC = () => {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const initial = user?.name ? user.name.charAt(0).toUpperCase() : '?';

  return (
    <div className="animate-in fade-in slide-in-from-bottom-2 p-6 duration-300 md:p-8">
      <div className="mb-8">
        <p className="text-sm text-muted-foreground">{t('settings.profile_desc')}</p>
      </div>

      <div className="max-w-2xl space-y-8">
        <section className="flex items-center gap-6">
          <div className="flex h-24 w-24 shrink-0 items-center justify-center rounded-full border-4 border-background bg-gradient-to-br from-primary to-primary/60 shadow-md">
            <span className="text-3xl font-bold text-primary-foreground">{initial}</span>
          </div>
          <div className="space-y-1">
            <h4 className="text-xl font-bold tracking-tight">{user?.name || '—'}</h4>
            <div className="flex items-center gap-1 text-sm text-muted-foreground">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
              {t('settings.profile_section.account_active')}
            </div>
          </div>
        </section>

        <div className="border-t border-border/40" />

        <section className="space-y-6">
          <Field
            icon={UserIcon}
            label={t('settings.profile_section.name')}
            value={user?.name ?? ''}
          />
          <Field
            icon={Mail}
            label={t('settings.profile_section.email')}
            value={user?.email ?? ''}
          />
          <Field
            icon={AtSign}
            label={t('settings.profile_section.username')}
            value={user?.username ?? ''}
          />
          <Field
            icon={Shield}
            label={t('settings.profile_section.role')}
            value={
              user?.is_superuser
                ? t('settings.profile_section.role_superuser')
                : t('settings.profile_section.role_member')
            }
          />
        </section>
      </div>
    </div>
  );
};
