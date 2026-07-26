import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, UserPlus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  useProject,
  useProjectMembers,
  useRemoveMember,
  useUpdateMemberRole,
} from '@/hooks/useProjectQuery';
import { useAuthStore } from '@/store/authStore';
import type { ProjectMemberDetail } from '@/types/project';
import { InviteMemberDialog } from '@modules/project/components/InviteMemberDialog';

export function ProjectDetailPage() {
  const { id = '' } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const { data: project, isLoading: projectLoading } = useProject(id);
  const { data: members, isLoading: membersLoading } = useProjectMembers(id);
  const updateRole = useUpdateMemberRole(id);
  const removeMember = useRemoveMember(id);

  const [inviteOpen, setInviteOpen] = useState(false);
  const [toRemove, setToRemove] = useState<ProjectMemberDetail | null>(null);

  // The current user's own role in this project drives what controls show.
  // Superusers act as owner (backend also bypasses gating for them).
  const myRole = useMemo(() => {
    if (user?.is_superuser) return 'owner';
    return members?.items.find((m) => m.user_id === user?.id)?.role ?? '';
  }, [members, user]);

  const canManage = myRole === 'owner' || myRole === 'manager';
  const canGrantOwner = myRole === 'owner';

  const roleBadgeVariant = (role: string) =>
    role === 'owner' ? 'default' : role === 'manager' ? 'secondary' : 'outline';

  return (
    <div className="p-6 md:p-8">
      <Button
        variant="ghost"
        size="sm"
        className="mb-4 -ml-2"
        onClick={() => navigate('/projects')}
      >
        <ArrowLeft className="mr-1 h-4 w-4" />
        {t('projects.back_to_list')}
      </Button>

      {projectLoading ? (
        <Skeleton className="mb-6 h-20 w-full max-w-lg" />
      ) : project ? (
        <div className="mb-8">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">{project.name}</h1>
            <Badge variant="outline" className="font-mono text-xs">
              {project.code}
            </Badge>
          </div>
          {project.description && (
            <p className="mt-1 text-sm text-muted-foreground">{project.description}</p>
          )}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t('projects.not_found')}</p>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">{t('projects.members_title')}</CardTitle>
          {canManage && (
            <Button size="sm" onClick={() => setInviteOpen(true)}>
              <UserPlus className="mr-1 h-4 w-4" />
              {t('projects.invite_title')}
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {membersLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('projects.member_name')}</TableHead>
                  <TableHead>{t('projects.member_email')}</TableHead>
                  <TableHead>{t('projects.member_role')}</TableHead>
                  {canManage && <TableHead className="text-right">{t('common.actions')}</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {members?.items.map((m) => {
                  const isSelf = m.user_id === user?.id;
                  // Only an owner may change/revoke an owner's role.
                  const canEditThis = canManage && (m.role !== 'owner' || canGrantOwner);
                  return (
                    <TableRow key={m.id}>
                      <TableCell>{m.name ?? '—'}</TableCell>
                      <TableCell className="text-muted-foreground">{m.email ?? '—'}</TableCell>
                      <TableCell>
                        {canEditThis && !isSelf ? (
                          <Select
                            value={m.role}
                            onValueChange={(role) => updateRole.mutate({ userId: m.user_id, role })}
                          >
                            <SelectTrigger className="h-8 w-32">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="member">{t('projects.role_member')}</SelectItem>
                              <SelectItem value="manager">{t('projects.role_manager')}</SelectItem>
                              {canGrantOwner && (
                                <SelectItem value="owner">{t('projects.role_owner')}</SelectItem>
                              )}
                            </SelectContent>
                          </Select>
                        ) : (
                          <Badge variant={roleBadgeVariant(m.role)}>
                            {t(`projects.role_${m.role}`)}
                          </Badge>
                        )}
                      </TableCell>
                      {canManage && (
                        <TableCell className="text-right">
                          {canEditThis && !isSelf && (
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8 text-destructive"
                              onClick={() => setToRemove(m)}
                              aria-label={t('common.remove')}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </TableCell>
                      )}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <InviteMemberDialog
        projectId={id}
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        canGrantOwner={canGrantOwner}
      />

      <ConfirmDialog
        open={!!toRemove}
        onOpenChange={(o) => !o && setToRemove(null)}
        title={t('projects.remove_member_title')}
        description={t('projects.remove_member_confirm', {
          name: toRemove?.name ?? toRemove?.email ?? '',
        })}
        confirmLabel={t('common.remove')}
        cancelLabel={t('common.cancel')}
        destructive
        loading={removeMember.isPending}
        onConfirm={async () => {
          if (toRemove) await removeMember.mutateAsync(toRemove.user_id);
          setToRemove(null);
        }}
      />
    </div>
  );
}
