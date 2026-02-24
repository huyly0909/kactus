export interface User {
    id: string;
    email: string;
    name: string;
    role: Role;
    permissions: Permission[];
    avatarUrl?: string;
}

export type Role = 'admin' | 'manager' | 'analyst' | 'viewer';

export type Permission =
    | 'read:reports'
    | 'write:reports'
    | 'read:transactions'
    | 'write:transactions'
    | 'manage:users'
    | 'manage:settings';

export interface AuthTokens {
    accessToken: string;
    refreshToken: string;
}

export interface LoginRequest {
    email: string;
    password: string;
}

export interface LoginResponse {
    user: User;
    tokens: AuthTokens;
}
