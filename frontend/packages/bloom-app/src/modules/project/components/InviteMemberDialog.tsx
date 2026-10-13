import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useAddMember, useAssignOwner } from '@/hooks/useProjectQuery';

interface Props {
  projectId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Only an OWNER may grant the OWNER role (backend also enforces this). */
  canGrantOwner: boolean;
  /**
   * `assign-owner` repairs a project that has lost its owner: the role picker
   * disappears and the submit goes to `POST /owner` instead of `POST /members`.
   * That is not cosmetic — `addMember` 409s on someone who is already a member,
   * and the project may have no members at all to pick from.
   */
  mode?: 'invite' | 'assign-owner';
}

/**
 * Invite an existing user by exact email + role, or (in `assign-owner` mode)
 * hand a project its owner back.
 *
 * There is deliberately no email search/autocomplete — the backend exposes no
 * endpoint to enumerate the user directory, so the inviter must know the address.
 */
export function InviteMemberDialog({
  projectId,
  open,
  onOpenChange,
  canGrantOwner,
  mode = 'invite',
}: Props) {
  const { t } = useTranslation();
  const add = useAddMember(projectId);
  const assignOwner = useAssignOwner(projectId);
  const isAssign = mode === 'assign-owner';

  const schema = z.object({
    email: z.string().trim().min(1, t('errors.required')).email(t('errors.invalid_email')),
    role: z.enum(['member', 'manager', 'owner']),
  });
  type FormValues = z.infer<typeof schema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', role: 'member' },
  });

  const handleOpenChange = (o: boolean) => {
    if (!o) form.reset();
    onOpenChange(o);
  };

  const onSubmit = async (values: FormValues) => {
    if (isAssign) {
      await assignOwner.mutateAsync(values.email);
    } else {
      await add.mutateAsync({ email: values.email, role: values.role });
    }
    form.reset();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isAssign ? t('projects.assign_owner') : t('projects.invite_title')}
          </DialogTitle>
          <DialogDescription>
            {isAssign ? t('projects.assign_owner_hint') : t('projects.invite_hint')}
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('projects.member_email')}</FormLabel>
                  <FormControl>
                    <Input type="email" autoComplete="off" autoFocus {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {/* No role picker when assigning an owner — the role *is* the point. */}
            <FormField
              control={form.control}
              name="role"
              render={({ field }) => (
                <FormItem className={isAssign ? 'hidden' : undefined}>
                  <FormLabel>{t('projects.member_role')}</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="member">{t('projects.role_member')}</SelectItem>
                      <SelectItem value="manager">{t('projects.role_manager')}</SelectItem>
                      {canGrantOwner && (
                        <SelectItem value="owner">{t('projects.role_owner')}</SelectItem>
                      )}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
                {t('common.cancel')}
              </Button>
              <Button type="submit" disabled={add.isPending || assignOwner.isPending}>
                {isAssign ? t('projects.assign_owner_submit') : t('projects.invite_submit')}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
