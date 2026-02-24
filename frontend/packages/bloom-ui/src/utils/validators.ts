import { z } from 'zod';

/** Common email validation */
export const emailSchema = z.string().email('Invalid email address');

/** Password: min 8 chars, at least one number and one uppercase */
export const passwordSchema = z
    .string()
    .min(8, 'Password must be at least 8 characters')
    .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
    .regex(/[0-9]/, 'Password must contain at least one number');

/** Positive number (for financial amounts) */
export const positiveNumberSchema = z
    .number()
    .positive('Must be a positive number');

/** Non-empty string */
export const requiredStringSchema = z
    .string()
    .min(1, 'This field is required');

/** Login form schema */
export const loginSchema = z.object({
    email: emailSchema,
    password: z.string().min(1, 'Password is required'),
});

export type LoginFormData = z.infer<typeof loginSchema>;
