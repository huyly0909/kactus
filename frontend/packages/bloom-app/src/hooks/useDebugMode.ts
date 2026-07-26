import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useDebugStore } from '@/store/debugStore';
import { useIsAdmin } from '@/hooks/useIsAdmin';

// Double gate: a non-admin flipping the persisted flag in DevTools/localStorage
// still resolves to false here, because debug UI is superuser-only.
export function useDebugMode(): boolean {
  const enabled = useDebugStore((s) => s.enabled);
  const isAdmin = useIsAdmin();
  return enabled && isAdmin;
}

// Syncs the `?bugbug` query param into the debug store (admins only). Must be
// called inside router context — mounted once in AppRoutes.
export function useDebugUrlSync(): void {
  const [params] = useSearchParams();
  const set = useDebugStore((s) => s.set);
  const isAdmin = useIsAdmin();
  useEffect(() => {
    if (!isAdmin) return;
    if (!params.has('bugbug')) return;
    // Bare `?bugbug` (raw === "") or any value other than an explicit off turns it on.
    const raw = params.get('bugbug');
    set(raw !== '0' && raw !== 'false');
  }, [params, set, isAdmin]);
}
