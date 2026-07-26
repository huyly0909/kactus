import type { PermissionItem } from './auth';

export interface Project {
  id: string;
  name: string;
  code: string;
  description?: string;
  status: string;
  created_by?: string;
}

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
