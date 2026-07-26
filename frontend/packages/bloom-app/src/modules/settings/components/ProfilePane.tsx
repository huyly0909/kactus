import { type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { User } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { useAuthStore } from '@/store/authStore';

interface FieldProps {
  label: string;
  value: string;
}

const Field: FC<FieldProps> = ({ label, value }) => (
  <div className="flex flex-col gap-0.5">
    <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
      {label}
    </span>
    <span className="text-sm text-foreground">{value || '—'}</span>
  </div>
);

export const ProfilePane: FC = () => {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t('settings.profile')}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div className="flex items-center gap-4">
          <Avatar className="h-14 w-14">
            <AvatarFallback className="text-lg">
              {user?.name ? user.name.charAt(0).toUpperCase() : <User className="h-6 w-6" />}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <p className="truncate text-lg font-semibold text-foreground">{user?.name || '—'}</p>
            <p className="truncate text-sm text-muted-foreground">{user?.email || '—'}</p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('settings.profile_section.name')} value={user?.name ?? ''} />
          <Field label={t('settings.profile_section.email')} value={user?.email ?? ''} />
          <Field label={t('settings.profile_section.username')} value={user?.username ?? ''} />
          <Field
            label={t('settings.profile_section.role')}
            value={
              user?.is_superuser
                ? t('settings.profile_section.role_superuser')
                : t('settings.profile_section.role_member')
            }
          />
        </div>
      </CardContent>
    </Card>
  );
};
