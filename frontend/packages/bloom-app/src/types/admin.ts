import type { PermissionItem } from './auth';

/** A user row as returned by the admin endpoints (backend `UserInfo`). */
export interface AdminUser {
  id: string;
  email: string;
  username?: string;
  name: string;
  status: string;
  is_superuser: boolean;
}

export interface CreateUserPayload {
  email: string;
  name: string;
  password: string;
  is_superuser?: boolean;
}

export interface UpdateUserRolePayload {
  is_superuser: boolean;
}

export interface ResetPasswordResponse {
  new_password: string;
}

/** Casbin role → permissions mapping from `GET /api/admin/authorization`. */
export type AuthorizationMap = Record<string, PermissionItem[]>;
