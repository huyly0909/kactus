import * as React from 'react';
import * as LabelPrimitive from '@radix-ui/react-label';
import { Slot } from '@radix-ui/react-slot';
import {
  Controller,
  FormProvider,
  useFormContext,
  type ControllerProps,
  type FieldPath,
  type FieldValues,
} from 'react-hook-form';
import { cn } from '@/lib/utils';
import { Label } from '@/components/ui/label';

const Form = FormProvider;

interface FormFieldContextValue<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
> {
  name: TName;
}

const FormFieldContext = React.createContext<FormFieldContextValue>({} as FormFieldContextValue);

function FormField<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
>(props: ControllerProps<TFieldValues, TName>) {
  return (
    <FormFieldContext.Provider value={{ name: props.name }}>
      <Controller {...props} />
    </FormFieldContext.Provider>
  );
}

interface FormItemContextValue {
  id: string;
}

const FormItemContext = React.createContext<FormItemContextValue>({} as FormItemContextValue);

function useFormField() {
  const fieldContext = React.useContext(FormFieldContext);
  const itemContext = React.useContext(FormItemContext);
  const { getFieldState, formState } = useFormContext();

  const fieldState = getFieldState(fieldContext.name, formState);

  if (!fieldContext) {
    throw new Error('useFormField should be used within <FormField>');
  }

  const { id } = itemContext;

  return {
    id,
    name: fieldContext.name,
    formItemId: `${id}-form-item`,
    formDescriptionId: `${id}-form-item-description`,
    formMessageId: `${id}-form-item-message`,
    ...fieldState,
  };
}

const FormItem = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => {
    const id = React.useId();
    return (
      <FormItemContext.Provider value={{ id }}>
        <div ref={ref} className={cn('space-y-2', className)} {...props} />
      </FormItemContext.Provider>
    );
  },
);
FormItem.displayName = 'FormItem';

const FormLabel = React.forwardRef<
  React.ComponentRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => {
  const { error, formItemId } = useFormField();
  return (
    <Label
      ref={ref}
      className={cn(error && 'text-destructive', className)}
      htmlFor={formItemId}
      {...props}
    />
  );
});
FormLabel.displayName = 'FormLabel';

const FormControl = React.forwardRef<
  React.ComponentRef<typeof Slot>,
  React.ComponentPropsWithoutRef<typeof Slot>
>(({ ...props }, ref) => {
  const { error, formItemId, formDescriptionId, formMessageId } = useFormField();
  return (
    <Slot
      ref={ref}
      id={formItemId}
      aria-describedby={!error ? formDescriptionId : `${formDescriptionId} ${formMessageId}`}
      aria-invalid={!!error}
      {...props}
    />
  );
});
FormControl.displayName = 'FormControl';

const FormDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => {
  const { formDescriptionId } = useFormField();
  return (
    <p
      ref={ref}
      id={formDescriptionId}
      className={cn('text-xs text-muted-foreground', className)}
      {...props}
    />
  );
});
FormDescription.displayName = 'FormDescription';

const FormMessage = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, children, ...props }, ref) => {
  const { error, formMessageId } = useFormField();
  const body = error ? String(error?.message ?? '') : children;

  if (!body) return null;

  return (
    <p
      ref={ref}
      id={formMessageId}
      className={cn('text-xs font-medium text-destructive', className)}
      {...props}
    >
      {body}
    </p>
  );
});
FormMessage.displayName = 'FormMessage';

interface FieldRowProps {
  label: React.ReactNode;
  /** Small grey line under the label — format rules, units, constraints. */
  hint?: React.ReactNode;
  /** Static text pinned to the right of the control (a unit, a computed echo). */
  suffix?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

/**
 * A flat label-left form row: 140px label column + value column, no card, no
 * border. This is the entity-page counterpart of `FormItem` (which stays the
 * label-above shape used inside dialogs).
 *
 * Goes *inside* `FormField`'s render, replacing `FormItem` — it provides its
 * own `FormItemContext` (so `FormControl` still gets a matching id) and renders
 * `FormMessage` itself in the value column, which makes the "row and message
 * both print the error" duplication impossible.
 *
 *   <FormField control={form.control} name="code" render={({ field }) => (
 *     <FieldRow label={t('projects.code')} hint={t('projects.code_format')}>
 *       <FormControl><Input {...field} /></FormControl>
 *     </FieldRow>
 *   )} />
 */
const FieldRow: React.FC<FieldRowProps> = ({ label, hint, suffix, children, className }) => {
  const id = React.useId();
  return (
    <FormItemContext.Provider value={{ id }}>
      {/* minmax(0,1fr), not 1fr: a bare 1fr track has min-width:auto, so a long
          nowrap value overruns its column instead of truncating. */}
      <div
        className={cn(
          'grid grid-cols-1 items-start gap-x-3 gap-y-1 py-1.5 text-sm sm:grid-cols-[140px_minmax(0,1fr)]',
          className,
        )}
      >
        <div className="flex flex-col pt-1.5 text-muted-foreground">
          <FormLabel className="font-normal">{label}</FormLabel>
          {hint && <span className="mt-0.5 text-[11px] text-muted-foreground/70">{hint}</span>}
        </div>
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <div className="min-w-0 flex-1">{children}</div>
            {suffix && <span className="shrink-0 text-xs text-muted-foreground">{suffix}</span>}
          </div>
          <FormMessage />
        </div>
      </div>
    </FormItemContext.Provider>
  );
};

export {
  useFormField,
  Form,
  FieldRow,
  FormItem,
  FormLabel,
  FormControl,
  FormDescription,
  FormMessage,
  FormField,
};
