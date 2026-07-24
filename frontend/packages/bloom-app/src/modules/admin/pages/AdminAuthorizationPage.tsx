import { useTranslation } from 'react-i18next';
import { ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAdminAuthorization } from '@/hooks/useAdminQuery';
import type { PermissionAct } from '@/types/auth';

const ACT_VARIANT: Record<string, 'secondary' | 'warning' | 'danger'> = {
  read: 'secondary',
  write: 'warning',
  manage: 'danger',
};

/** Casbin role → permission mapping (read-only, superuser only). */
export function AdminAuthorizationPage() {
  const { t } = useTranslation();
  const { data, isLoading } = useAdminAuthorization();

  const roles = Object.entries(data ?? {});

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">{t('admin.authorization.title')}</h1>
        <p className="text-sm text-muted-foreground">{t('admin.authorization.subtitle')}</p>
      </div>

      {isLoading && <Skeleton className="h-40 w-full" />}

      {!isLoading && roles.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16 text-center">
          <ShieldCheck className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t('admin.authorization.empty')}</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {roles.map(([role, permissions]) => (
          <Card key={role}>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle className="flex items-center gap-2 text-base">
                <ShieldCheck className="h-4 w-4 text-primary" />
                {role}
              </CardTitle>
              <Badge variant="outline">
                {t('admin.authorization.permission_count', { total: permissions.length })}
              </Badge>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="border-t-0">
                    <TableHead>{t('admin.authorization.permission')}</TableHead>
                    <TableHead className="text-right">{t('admin.authorization.act')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {permissions.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={2} className="py-6 text-center text-muted-foreground">
                        {t('common.no_data')}
                      </TableCell>
                    </TableRow>
                  ) : (
                    permissions.map((p: { permission: string; act: PermissionAct }) => (
                      <TableRow key={`${p.permission}:${p.act}`}>
                        <TableCell className="font-mono text-xs">{p.permission}</TableCell>
                        <TableCell className="text-right">
                          <Badge variant={ACT_VARIANT[p.act] ?? 'secondary'}>{p.act}</Badge>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
