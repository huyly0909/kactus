import type { PermissionItem } from './auth';

export interface Project {
  id: string;
  name: string;
  code: string;
  description?: string;
  status: string;
  created_by?: string;
  /** UTC, tz-aware — render with `useFormatDateTime()`, never `toLocaleString()`. */
  create_time?: string;
  /** Derived server-side from the OWNER membership (or `created_by`). */
  owner_id?: string | null;
  owner_name?: string | null;
  owner_email?: string | null;
  /**
   * True only when a real OWNER membership backs the fields above. When false
   * they may still be filled in — from `created_by`, who *created* the project
   * but may hold no role in it. Branch on this, never on `owner_name != null`,
   * or an unassigned project renders as owned. See `<ProjectOwner />`.
   */
  has_owner?: boolean;
  /** `FancyInt` — arrives as a string; `Number()` it before comparing. */
  member_count?: string;
  /** The requesting user's role here; null for a superuser listing. */
  my_role?: string | null;
}

/** `Project.status` values — the archive filter's domain. */
export type ProjectStatus = 'active' | 'archived';

export interface ProjectMember {
  id: string;
  project_id: string;
  user_id: string;
  role: string;
}

/** A member enriched with the user's email/name for display. */
export interface ProjectMemberDetail extends ProjectMember {
  email?: string;
  name?: string;
}

export interface PermissionsResponse {
  project_id: string;
  permissions: PermissionItem[];
  role: string | null;
  is_superuser: boolean;
}
