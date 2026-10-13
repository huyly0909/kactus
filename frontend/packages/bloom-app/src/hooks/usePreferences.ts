import { useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { authService, type PreferencesPayload } from '@/services/authService';
import { useAuthStore } from '@/store/authStore';
import { setLanguage } from '@/i18n';

/** Default timezone when the user has none saved (VN-based product). */
export const DEFAULT_TIMEZONE = 'Asia/Ho_Chi_Minh';

/**
 * Persist the current user's UI preferences (language / timezone) to their
 * account via PATCH /api/auth/me. On success the returned user is written back
 * into the auth store and the language is applied immediately, so the change
 * survives a reload (the account is the source of truth, not localStorage).
 */
export function useUpdatePreferences() {
  const { t } = useTranslation();
  const setUser = useAuthStore((s) => s.setUser);
  return useMutation({
    mutationFn: (payload: PreferencesPayload) => authService.updatePreferences(payload),
    onSuccess: (user) => {
      setUser(user);
      if (user.language) void setLanguage(user.language);
      toast.success(t('common.update_success'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}
