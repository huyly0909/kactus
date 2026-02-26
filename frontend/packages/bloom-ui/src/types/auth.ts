export interface User {
  id: string;
  email: string;
  username: string;
  name: string;
  status: string;
  is_superuser: boolean;
  avatarUrl?: string;
}

export type Role = 'owner' | 'manager' | 'member';

export type PermissionAct = 'read' | 'write' | 'manage';

export interface PermissionItem {
  permission: string;
  act: PermissionAct;
}

export interface LoginRequest {
  email: string;
  password: string;
  remember?: boolean;
}

export interface LoginResponse {
  user: User;
}
