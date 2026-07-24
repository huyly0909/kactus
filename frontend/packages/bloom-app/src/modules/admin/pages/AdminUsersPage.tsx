import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { KeyRound, Plus, ShieldCheck, ShieldOff, UserX } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { useAuth } from '@/hooks/useAuth';
import {
  useAdminUsers,
  useDeactivateUser,
  useResetPassword,
  useUpdateUserRole,
} from '@/hooks/useAdminQuery';
import { CreateUserDialog } from '@modules/admin/components/CreateUserDialog';
import { NewPasswordDialog } from '@modules/admin/components/NewPasswordDialog';
import type { AdminUser } from '@/types/admin';

type PendingAction = { kind: 'role' | 'reset' | 'deactivate'; user: AdminUser };

/** User management (superuser only) — list, create, role, reset password, deactivate. */
export function AdminUsersPage() {
  const { t } = useTranslation();
  const { user: currentUser } = useAuth();
  const { data, isLoading } = useAdminUsers();

  const [createOpen, setCreateOpen] = useState(false);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [newPassword, setNewPassword] = useState<{ name: string; password: string } | null>(null);

  const updateRole = useUpdateUserRole();
  const resetPassword = useResetPassword();
  const deactivate = useDeactivateUser();

  const isBusy = updateRole.isPending || resetPassword.isPending || deactivate.isPending;

  const handleConfirm = async () => {
    if (!pending) return;
    const { kind, user } = pending;
    try {
      if (kind === 'role') {
        await updateRole.mutateAsync({ userId: user.id, isSuperuser: !user.is_superuser });
      } else if (kind === 'deactivate') {
        await deactivate.mutateAsync(user.id);
      } else {
        const result = await resetPassword.mutateAsync(user.id);
        setNewPassword({ name: user.name, password: result.new_password });
      }
    } finally {
      setPending(null);
    }
  };

  const confirmCopy = (action: PendingAction) => {
    if (action.kind === 'role') {
      return action.user.is_superuser
        ? {
            title: t('admin.users.revoke_superuser'),
            description: t('admin.users.revoke_superuser_confirm', { name: action.user.name }),
            destructive: true,
          }
        : {
            title: t('admin.users.make_superuser'),
            description: t('admin.users.make_superuser_confirm', { name: action.user.name }),
            destructive: false,
          };
    }
    if (action.kind === 'deactivate') {
      return {
        title: t('admin.users.deactivate'),
        description: t('admin.users.deactivate_confirm', { name: action.user.name }),
        destructive: true,
      };
    }
    return {
      title: t('admin.users.reset_password'),
      description: t('admin.users.reset_password_confirm', { name: action.user.name }),
      destructive: false,
    };
  };

  const columns: DataTableColumn<AdminUser>[] = [
    { key: 'name', title: t('admin.users.name'), className: 'font-medium' },
    {
      key: 'email',
      title: t('admin.users.email'),
      render: (u) => <span className="text-muted-foreground">{u.email}</span>,
    },
    {
      key: 'is_superuser',
      title: t('admin.users.role'),
      render: (u) => (
        <Badge variant={u.is_superuser ? 'default' : 'outline'}>
          {u.is_superuser ? t('admin.users.role_superuser') : t('admin.users.role_member')}
        </Badge>
      ),
    },
    {
      key: 'status',
      title: t('admin.users.status'),
      render: (u) => (
        <Badge variant={u.status === 'active' ? 'success' : 'secondary'}>
          {u.status === 'active' ? t('common.active') : t('common.inactive')}
        </Badge>
      ),
    },
    {
      key: 'actions',
      title: t('common.actions'),
      className: 'text-right',
      render: (u) => {
        const isSelf = currentUser?.id === u.id;
        return (
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              title={
                u.is_superuser ? t('admin.users.revoke_superuser') : t('admin.users.make_superuser')
              }
              disabled={isSelf || isBusy}
              onClick={() => setPending({ kind: 'role', user: u })}
            >
              {u.is_superuser ? (
                <ShieldOff className="h-4 w-4" />
              ) : (
                <ShieldCheck className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              title={t('admin.users.reset_password')}
              disabled={isBusy}
              onClick={() => setPending({ kind: 'reset', user: u })}
            >
              <KeyRound className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              title={t('admin.users.deactivate')}
              className="text-destructive hover:text-destructive"
              disabled={isSelf || isBusy || u.status !== 'active'}
              onClick={() => setPending({ kind: 'deactivate', user: u })}
            >
              <UserX className="h-4 w-4" />
            </Button>
          </div>
        );
      },
    },
  ];

  const copy = pending ? confirmCopy(pending) : null;

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('admin.users.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('admin.users.subtitle')}</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-1 h-4 w-4" />
          {t('admin.users.create_title')}
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        searchable
        searchPlaceholder={t('common.search')}
        emptyMessage={t('admin.users.empty')}
        getRowKey={(u) => u.id}
      />

      <CreateUserDialog open={createOpen} onOpenChange={setCreateOpen} />

      {pending && copy && (
        <ConfirmDialog
          open
          onOpenChange={(o) => !o && setPending(null)}
          title={copy.title}
          description={copy.description}
          destructive={copy.destructive}
          confirmLabel={t('common.confirm')}
          cancelLabel={t('common.cancel')}
          loading={isBusy}
          onConfirm={handleConfirm}
        />
      )}

      {newPassword && (
        <NewPasswordDialog
          open
          onOpenChange={(o) => !o && setNewPassword(null)}
          userName={newPassword.name}
          password={newPassword.password}
        />
      )}
    </div>
  );
}
