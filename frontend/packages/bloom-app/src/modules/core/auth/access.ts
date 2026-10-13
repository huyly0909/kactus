import { usePermissionStore } from '@/store/permissionStore';
import type { NavPermission } from '@/lib/module-core';

// UX-only permission reader (the backend is the real boundary). Superuser always
// passes; otherwise the effective-permission list is matched. kactus has no
// call-site populating `permissions` yet, so today this only ever returns true
// for superusers — nav modules therefore lean on `adminOnly`/`debugOnly` gates.
export function usePermissionEvaluator(): (p: NavPermission) => boolean {
  const permissions = usePermissionStore((s) => s.permissions);
  const isSuperuser = usePermissionStore((s) => s.isSuperuser);
  return (p: NavPermission) => {
    if (isSuperuser) return true;
    return permissions.some((x) => x.permission === p.permission && x.act === p.action);
  };
}
