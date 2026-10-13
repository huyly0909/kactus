import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Crown, FolderGit2, Trash2, UserPlus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { BareSection } from '@/components/ui/bare-section';
import { EntityPage, EntityPageBody, EntityPageHeader } from '@/components/ui/entity-page';
import { Skeleton } from '@/components/ui/skeleton';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Input } from '@/components/ui/input';
import { FieldRow, FormControl, FormField } from '@/components/ui/form';
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
import { useFormatDateTime } from '@/hooks/useFormatDateTime';
import {
  useProject,
  useProjectMembers,
  useRemoveMember,
  useUpdateMemberRole,
  useUpdateProject,
} from '@/hooks/useProjectQuery';
import {
  projectDisplayName,
  projectFormSchema,
  projectMemberCount,
  type ProjectFormValues,
} from '@/lib/project';
import { useAuthStore } from '@/store/authStore';
import { useProjectStore } from '@/store/projectStore';
import type { ProjectMemberDetail } from '@/types/project';
import { InviteMemberDialog } from '@modules/project/components/InviteMemberDialog';
import { ProjectOwner } from '@modules/project/components/ProjectOwner';

/**
 * One project: identity, edit form and members — reached by clicking a row on
 * the list, so the URL names what is on screen and the page can be linked to.
 *
 * Every control and every piece of state lives in the sticky bar at the top:
 * the archive kebab, Discard, Save, and Save's own disabled state reporting
 * whether there is anything to save. Nothing is in a footer. There is no
 * in-page back button either — TopHeader already renders one.
 */
export function ProjectDetailPage() {
  const { id = '' } = useParams();
  const { t } = useTranslation();
  const fmtDateTime = useFormatDateTime();
  const user = useAuthStore((s) => s.user);
  const currentProject = useProjectStore((s) => s.currentProject);
  const setProject = useProjectStore((s) => s.setProject);

  const { data: project, isLoading: projectLoading } = useProject(id);
  const { data: members, isLoading: membersLoading } = useProjectMembers(id);
  const updateRole = useUpdateMemberRole(id);
  const removeMember = useRemoveMember(id);
  const update = useUpdateProject(id);

  const [inviteOpen, setInviteOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);
  const [toRemove, setToRemove] = useState<ProjectMemberDetail | null>(null);

  // The API resolves the viewer's own membership, so gating no longer waits on
  // the members query. Superusers act as owner (the backend agrees).
  const myRole = user?.is_superuser ? 'owner' : (project?.my_role ?? '');
  const canManage = myRole === 'owner' || myRole === 'manager';
  const canGrantOwner = myRole === 'owner';
  const isArchived = project?.status === 'archived';

  const form = useForm<ProjectFormValues>({
    resolver: zodResolver(projectFormSchema(t)),
    defaultValues: { name: '', code: '', description: '' },
  });

  // Fill once the project arrives, and refill after a save so the form stops
  // reporting itself dirty against values the server has already accepted.
  const { reset } = form;
  useEffect(() => {
    if (!project) return;
    reset({
      name: project.name,
      code: project.code,
      description: project.description ?? '',
    });
  }, [project, reset]);

  const onSubmit = async (values: ProjectFormValues) => {
    try {
      const updated = await update.mutateAsync({
        name: values.name,
        code: values.code,
        description: values.description ?? '',
      });
      // Renaming the active project must refresh the sidebar chip too.
      if (currentProject?.id === updated.id) setProject(updated);
    } catch (err) {
      // A duplicate code is a field problem, not a page problem — the mutation
      // already toasted, but the message belongs under the input that caused it.
      const data = (err as { response?: { data?: { data?: { code?: string } } } })?.response?.data;
      if (data?.data?.code) form.setError('code', { message: t('projects.code_taken') });
    }
  };

  const roleBadgeVariant = (role: string) =>
    role === 'owner' ? 'default' : role === 'manager' ? 'secondary' : 'outline';

  if (!projectLoading && !project) {
    return (
      <EntityPage>
        <EntityPageHeader
          title={t('projects.not_found')}
          titleIcon={<FolderGit2 className="h-5 w-5 shrink-0 text-muted-foreground" />}
        />
      </EntityPage>
    );
  }

  return (
    <EntityPage form={form} onValid={onSubmit}>
      <EntityPageHeader
        isLoading={projectLoading}
        titleIcon={<FolderGit2 className="h-5 w-5 shrink-0 text-muted-foreground" />}
        title={project ? projectDisplayName(project) : ''}
        // Only a manager gets Discard/Save; only an owner may archive.
        onDiscard={canManage ? () => reset() : undefined}
        saveDisabled={update.isPending}
        archive={
          canGrantOwner && project
            ? {
                active: !isArchived,
                isPending: update.isPending,
                archiveLabel: t('projects.archive'),
                unarchiveLabel: t('projects.restore'),
                confirmText: t('projects.archive_confirm', {
                  name: projectDisplayName(project),
                }),
                onToggle: () => update.mutateAsync({ status: isArchived ? 'active' : 'archived' }),
              }
            : undefined
        }
      >
        <Badge variant={isArchived ? 'secondary' : 'success'}>
          {t(isArchived ? 'projects.status_archived' : 'projects.status_active')}
        </Badge>
      </EntityPageHeader>

      <EntityPageBody className="space-y-8">
        {projectLoading || !project ? (
          <Skeleton className="h-40 w-full max-w-2xl" />
        ) : (
          <>
            <BareSection title={t('projects.edit_title')}>
              <div className="max-w-2xl">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FieldRow label={t('projects.name')}>
                      <FormControl>
                        <Input disabled={!canManage} {...field} />
                      </FormControl>
                    </FieldRow>
                  )}
                />
                <FormField
                  control={form.control}
                  name="code"
                  render={({ field }) => (
                    <FieldRow label={t('projects.code')} hint={t('projects.code_format')}>
                      <FormControl>
                        <Input className="font-mono" disabled={!canManage} {...field} />
                      </FormControl>
                    </FieldRow>
                  )}
                />
                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FieldRow label={t('projects.description')}>
                      <FormControl>
                        <Input disabled={!canManage} {...field} />
                      </FormControl>
                    </FieldRow>
                  )}
                />
                {/* Read-only facts sit in the same 140px grid as the editable
                    fields — one column of labels, not a separate facts line. */}
                <FieldRow label={t('projects.owner_label')}>
                  <p className="pt-1.5 text-sm">
                    <ProjectOwner project={project} />
                  </p>
                </FieldRow>
                <FieldRow label={t('projects.col_members')}>
                  <p className="pt-1.5 text-sm tabular-nums">{projectMemberCount(project)}</p>
                </FieldRow>
                <FieldRow label={t('projects.col_created')}>
                  <p className="pt-1.5 text-sm tabular-nums">{fmtDateTime(project.create_time)}</p>
                </FieldRow>
              </div>
              {!canManage && (
                <p className="pt-2 text-xs text-muted-foreground">{t('projects.readonly_hint')}</p>
              )}
            </BareSection>

            <BareSection
              title={t('projects.members_title')}
              action={
                canManage && (
                  <div className="flex items-center gap-2">
                    {/* Only surfaced while the project is actually broken. It is
                        the one repair path that works with zero members — the
                        role Select below can only promote someone already here. */}
                    {!project.has_owner && canGrantOwner && (
                      <Button size="sm" variant="destructive" onClick={() => setAssignOpen(true)}>
                        <Crown className="h-4 w-4" />
                        {t('projects.assign_owner')}
                      </Button>
                    )}
                    <Button size="sm" onClick={() => setInviteOpen(true)}>
                      <UserPlus className="h-4 w-4" />
                      {t('projects.invite_title')}
                    </Button>
                  </div>
                )
              }
            >
              {membersLoading ? (
                <Skeleton className="h-24 w-full" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('projects.member_name')}</TableHead>
                      <TableHead>{t('projects.member_email')}</TableHead>
                      <TableHead>{t('projects.member_role')}</TableHead>
                      {canManage && (
                        <TableHead className="text-right">{t('common.actions')}</TableHead>
                      )}
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
                                onValueChange={(role) =>
                                  updateRole.mutate({ userId: m.user_id, role })
                                }
                              >
                                <SelectTrigger className="w-32">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="member">
                                    {t('projects.role_member')}
                                  </SelectItem>
                                  <SelectItem value="manager">
                                    {t('projects.role_manager')}
                                  </SelectItem>
                                  {canGrantOwner && (
                                    <SelectItem value="owner">
                                      {t('projects.role_owner')}
                                    </SelectItem>
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
                                  size="icon-sm"
                                  variant="ghost-destructive"
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
            </BareSection>
          </>
        )}
      </EntityPageBody>

      <InviteMemberDialog
        projectId={id}
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        canGrantOwner={canGrantOwner}
      />

      <InviteMemberDialog
        projectId={id}
        open={assignOpen}
        onOpenChange={setAssignOpen}
        canGrantOwner={canGrantOwner}
        mode="assign-owner"
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
    </EntityPage>
  );
}
