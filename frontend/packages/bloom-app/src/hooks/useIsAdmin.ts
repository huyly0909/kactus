import { useAuthStore } from '@/store/authStore';

/**
 * Whether the current user is a superuser — the kactus admin gate. Replaces
 * buitiful's PocketBase-backed `useIsAdmin`. Used to double-gate debug mode
 * (a non-admin flipping localStorage still resolves to non-admin here) and to
 * filter admin-only modules/nav.
 */
export function useIsAdmin(): boolean {
  return useAuthStore((s) => s.user?.is_superuser ?? false);
}
