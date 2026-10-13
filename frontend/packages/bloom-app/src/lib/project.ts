import { z } from 'zod';
import type { TFunction } from 'i18next';
import type { Project } from '@/types/project';

/**
 * Max length of `code`, mirroring the backend's `String(50)` column
 * (`PROJECT_CODE_MAX_LENGTH`). Over-long values are refused server-side too —
 * this only saves the round trip.
 */
export const PROJECT_CODE_MAX_LENGTH = 50;

/**
 * The create/edit form rules, shared by every project form.
 *
 * A factory rather than a constant because the messages come from `t`, and the
 * schema has to be rebuilt when the language changes. Mirrors the backend's
 * `_validate_code` — the server stays authoritative (it also owns uniqueness,
 * which no client can check).
 */
export const projectFormSchema = (t: TFunction) =>
  z.object({
    name: z.string().trim().min(1, t('errors.required')),
    code: z
      .string()
      .trim()
      .min(1, t('errors.required'))
      .max(PROJECT_CODE_MAX_LENGTH, t('projects.code_max'))
      .regex(/^[a-z0-9-]+$/, t('projects.code_format')),
    description: z.string().trim().optional(),
  });

/** Values of {@link projectFormSchema} — one type for both forms. */
export type ProjectFormValues = z.infer<ReturnType<typeof projectFormSchema>>;

/**
 * How a project is named anywhere it is shown to a user: `name <code>`.
 *
 * `name` alone is ambiguous — every auto-provisioned project is called "First
 * Project", so a switcher listing three of them says nothing. `code` is the
 * unique, mutable, human-readable identity (`user-<owner id>` for personal
 * projects), which makes the pair unambiguous without exposing the snowflake id.
 */
export const projectDisplayName = (project: Pick<Project, 'name' | 'code'>): string =>
  `${project.name} <${project.code}>`;

/** Whether the viewer owns this project — authoritative, from their membership. */
export const isProjectOwner = (project: Pick<Project, 'my_role'>): boolean =>
  project.my_role === 'owner';

/** Member count as a number — the API sends `FancyInt` as a string. */
export const projectMemberCount = (project: Pick<Project, 'member_count'>): number =>
  Number(project.member_count ?? 0);

/** Lifecycle filter for the projects list. `'all'` is not a `Project.status`. */
export type ProjectStatusFilter = 'active' | 'archived' | 'all';

/**
 * The list's row set: filter by lifecycle, then newest first.
 *
 * Sorting happens here because `DataTable` starts unsorted and has no
 * `defaultSort` prop — pre-sorting at the source is the established workaround.
 * Pure and exported so the default (archived hidden, newest first) is testable
 * without mounting the page.
 */
export const filterAndSortProjects = <T extends Pick<Project, 'status' | 'create_time'>>(
  projects: T[],
  status: ProjectStatusFilter,
): T[] =>
  projects
    .filter((p) => (status === 'all' ? true : p.status === status))
    .sort((a, b) => (b.create_time ?? '').localeCompare(a.create_time ?? ''));
