import * as React from 'react';
import { Archive, ArchiveRestore, Loader2, MoreHorizontal } from 'lucide-react';
import {
  useFormContext,
  useFormState,
  type FieldValues,
  type UseFormReturn,
} from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Form } from '@/components/ui/form';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

// The route-level shell for an entity-detail page: a full-bleed sticky header
// over a flat body. It reads "[title] [actions] … [status]" — record actions
// hug the title on the left, status badges are pushed to the far right. Save
// and Discard live in that header and nowhere else; this app has no form
// footers (a control the user must scroll to find reports nothing).
//
// EntityPage owns the <form>: pass `form` + `onValid` and the header's
// Discard/Save read `isDirty`/`isSubmitting` off context. Callers never thread
// form state through props. Omit `form` for a display-only detail page and no
// form actions render.
//
// Scroll model differs from a self-contained dialog on purpose: kactus has ONE
// scrollport per page (`main.flex-1.overflow-y-auto` in DashboardLayout), so
// the root is `min-h-full` and the header is `sticky top-0` against that outer
// scrollport — not `h-full min-h-0` with a scrolling body of its own.

interface EntityPageBaseProps {
  className?: string;
  children?: React.ReactNode;
}

interface EntityPageWithoutForm extends EntityPageBaseProps {
  form?: undefined;
  onValid?: undefined;
  formId?: undefined;
}

interface EntityPageWithForm<T extends FieldValues> extends EntityPageBaseProps {
  form: UseFormReturn<T>;
  onValid: (data: T) => Promise<unknown> | void;
  /** Only needed if something outside the page must target this form. */
  formId?: string;
}

export type EntityPageProps<T extends FieldValues = FieldValues> =
  | EntityPageWithoutForm
  | EntityPageWithForm<T>;

function EntityPage<T extends FieldValues>(props: EntityPageProps<T>) {
  const { className, children } = props;
  // `min-h-full`, never `h-full min-h-0`: the page must be allowed to grow past
  // the viewport and let `main` scroll it.
  const wrapper = cn('flex min-h-full flex-col', className);

  if (props.form) {
    const { form, onValid, formId } = props;
    return (
      <Form {...form}>
        <form
          id={formId}
          data-slot="entity-page"
          className={wrapper}
          onSubmit={form.handleSubmit(onValid)}
        >
          {children}
        </form>
      </Form>
    );
  }

  return (
    <div data-slot="entity-page" className={wrapper}>
      {children}
    </div>
  );
}

// Split out of EntityPageHeader so `useFormState` is only ever called inside a
// FormProvider — with no provider its `control` is null and the hook throws,
// which is exactly what a display-only header would hit.
const HeaderFormActions: React.FC<{
  onDiscard: () => void;
  isLoading?: boolean;
  saveDisabled?: boolean;
  saveLabel?: string;
  discardLabel?: string;
}> = ({ onDiscard, isLoading, saveDisabled, saveLabel, discardLabel }) => {
  const { t } = useTranslation();
  const { isDirty, isSubmitting } = useFormState();
  // Nothing to save, nothing to discard — the cluster stays hidden until the
  // form is dirty, so a read-through of the record has no live buttons on it.
  if (!isDirty) return null;
  return (
    <>
      {/* Discard resets the form to its loaded values; it does not navigate. */}
      <Button
        size="sm"
        variant="outline"
        className="min-w-20"
        onClick={onDiscard}
        disabled={isSubmitting}
      >
        {discardLabel ?? t('common.discard')}
      </Button>
      <Button
        type="submit"
        size="sm"
        className="min-w-20"
        disabled={isSubmitting || !!isLoading || !!saveDisabled}
      >
        {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
        {saveLabel ?? t('common.save')}
      </Button>
    </>
  );
};

export interface EntityPageArchive {
  /** `false` renders the archived banner and offers Restore instead of Archive. */
  active: boolean;
  onToggle: () => void | Promise<unknown>;
  isPending?: boolean;
  archiveLabel?: string;
  unarchiveLabel?: string;
  /** `null` skips the confirmation step. */
  confirmText?: string | null;
}

interface EntityPageHeaderProps {
  title?: React.ReactNode;
  titleIcon?: React.ReactNode;
  isLoading?: boolean;
  /** Presence of this enables the Discard/Save cluster. */
  onDiscard?: () => void;
  saveDisabled?: boolean;
  saveLabel?: string;
  discardLabel?: string;
  archive?: EntityPageArchive;
  /** Extra record-scoped actions, rendered in the LEFT cluster after Save. */
  extraActions?: React.ReactNode;
  /** Status badges — pushed to the far RIGHT. Never put an action here. */
  children?: React.ReactNode;
}

const EntityPageHeader: React.FC<EntityPageHeaderProps> = ({
  title,
  titleIcon,
  isLoading,
  onDiscard,
  saveDisabled,
  saveLabel,
  discardLabel,
  archive,
  extraActions,
  children,
}) => {
  const { t } = useTranslation();
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  // Detect a surrounding form via context rather than a prop. `useFormContext`
  // returns null outside a provider, which is safe; `useFormState` is not —
  // hence the HeaderFormActions split.
  const hasForm = !!useFormContext();
  const showFormActions = hasForm && !!onDiscard;
  const isArchived = !!archive && !archive.active;

  const archiveLabel = archive?.archiveLabel ?? t('common.archive');
  const unarchiveLabel = archive?.unarchiveLabel ?? t('common.unarchive');
  const confirmText =
    archive?.confirmText === undefined ? t('common.archive_confirm') : archive.confirmText;

  const runArchiveToggle = async () => {
    await archive?.onToggle();
  };

  // Archiving needs a confirm; restoring a soft-deleted record is benign and
  // fires directly — same path the banner's Restore button takes.
  const handleArchiveMenuClick = () => {
    if (!archive) return;
    if (archive.active && confirmText !== null) {
      setConfirmOpen(true);
      return;
    }
    void runArchiveToggle();
  };

  return (
    <div
      data-slot="entity-page-header"
      // `top-0`, not `top-14`: `main` IS the scrollport and TopHeader sits
      // outside it. `z-20`, not 30 — 30 would paint over popover content.
      // No backdrop-blur: `bg-card` is opaque and a backdrop-filter creates a
      // containing block that makes `sticky` flaky.
      className="sticky top-0 z-20 flex shrink-0 flex-col border-b border-border bg-card"
    >
      <div className="mx-auto flex w-full max-w-[100rem] flex-wrap items-center gap-x-3 gap-y-1.5 px-6 py-2 md:px-8">
        <h1 className="flex min-w-0 items-center gap-2 text-lg font-semibold text-foreground sm:text-xl">
          {titleIcon}
          {isLoading ? (
            <Skeleton className="inline-block h-7 w-64" />
          ) : (
            <span className="truncate">{title}</span>
          )}
          {/* The kebab is the ONE way to archive a record — it sits next to the
              title so it reads as "an operation on THIS record", separate from
              the form-scoped Discard/Save. */}
          {archive && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  className="shrink-0"
                  aria-label={t('common.more_actions')}
                  disabled={archive.isPending}
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="min-w-44">
                <DropdownMenuItem
                  variant={archive.active ? 'destructive' : 'default'}
                  onSelect={(e) => {
                    e.preventDefault();
                    handleArchiveMenuClick();
                  }}
                >
                  {archive.active ? <Archive /> : <ArchiveRestore />}
                  {archive.active ? archiveLabel : unarchiveLabel}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </h1>
        {/* LEFT — actions, hugging the title.
            `max-w-full` is load-bearing: `shrink-0` pins the cluster at
            max-content, so without it the container can never constrain it, its
            own `flex-wrap` never engages, and the last button ends up off-screen
            on a narrow viewport.
            `order-last sm:order-none` — once it wraps, each cluster takes its
            own line and the `ml-auto` status below would land alone on the last
            line, flush right against nothing. Dropping the actions to the bottom
            lets status ride up onto the title row instead. */}
        {(showFormActions || extraActions) && (
          <div className="order-last flex max-w-full shrink-0 flex-wrap items-center gap-2 sm:order-none">
            {showFormActions && (
              <HeaderFormActions
                onDiscard={onDiscard}
                isLoading={isLoading}
                saveDisabled={saveDisabled}
                saveLabel={saveLabel}
                discardLabel={discardLabel}
              />
            )}
            {extraActions}
          </div>
        )}
        {/* RIGHT — status only. */}
        {children && (
          <div className="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-2">
            {children}
          </div>
        )}
      </div>

      {/* Archived banner. Restore sits on the banner itself because when a
          record IS archived, restoring it is the dominant action. */}
      {isArchived && (
        <div className="border-t border-destructive/30 bg-destructive/10">
          <div className="mx-auto flex w-full max-w-[100rem] flex-wrap items-center gap-3 px-6 py-2 text-sm text-destructive md:px-8">
            <Archive className="h-4 w-4 shrink-0" />
            <span className="flex-1">{t('common.archived_banner')}</span>
            <Button
              size="sm"
              variant="outline"
              disabled={archive?.isPending}
              onClick={() => void runArchiveToggle()}
            >
              <ArchiveRestore className="h-4 w-4" />
              {unarchiveLabel}
            </Button>
          </div>
        </div>
      )}

      {archive && (
        <ConfirmDialog
          open={confirmOpen}
          onOpenChange={setConfirmOpen}
          destructive
          title={archiveLabel}
          description={confirmText ?? undefined}
          confirmLabel={archiveLabel}
          cancelLabel={t('common.cancel')}
          loading={archive.isPending}
          onConfirm={async () => {
            await runArchiveToggle();
            setConfirmOpen(false);
          }}
        />
      )}
    </div>
  );
};

const EntityPageBody: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => (
  <div data-slot="entity-page-body" className="flex-1" {...props}>
    {/* Inner wrapper caps and centers the content column on wide monitors;
        padding lives here so EntityPageToolbar's negative-margin bleed lands on
        this column's padding edge. */}
    <div className={cn('mx-auto w-full max-w-[100rem] px-6 py-8 md:px-8', className)}>
      {children}
    </div>
  </div>
);

export interface EntityPageToolbarProps {
  /** State actions (Confirm / Print / transitions) — LEFT. */
  actions?: React.ReactNode;
  /** State display — RIGHT. */
  status?: React.ReactNode;
  className?: string;
}

// Sits at the top of EntityPageBody, not in the header chrome: business
// actions and state live here, form persistence (Save/Discard) stays above.
const EntityPageToolbar: React.FC<EntityPageToolbarProps> = ({ actions, status, className }) => (
  <div
    data-slot="entity-page-toolbar"
    className={cn(
      '-mx-6 -mt-8 mb-8 flex flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-6 py-3 md:-mx-8 md:px-8',
      className,
    )}
  >
    <div className="flex flex-wrap items-center gap-2">{actions}</div>
    <div className="flex flex-wrap items-center gap-2">{status}</div>
  </div>
);

export { EntityPage, EntityPageBody, EntityPageHeader, EntityPageToolbar };
