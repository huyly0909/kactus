import { Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ShieldAlert } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';

/**
 * Layout route for `/admin/*` — renders the nested admin pages only for
 * superusers. The backend enforces this too; this is UX, not security.
 */
export function AdminGuard() {
  const { t } = useTranslation();
  const { user } = useAuth();

  if (!user?.is_superuser) {
    return (
      <div className="flex flex-col items-center justify-center p-16 text-center">
        <ShieldAlert className="mb-3 h-10 w-10 text-muted-foreground" />
        <h2 className="text-lg font-semibold">{t('admin.forbidden_title')}</h2>
        <p className="text-sm text-muted-foreground">{t('admin.forbidden_message')}</p>
      </div>
    );
  }

  return <Outlet />;
}
