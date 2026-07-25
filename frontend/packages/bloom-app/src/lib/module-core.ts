import type React from 'react';

export type NavItemType = 'link' | 'dropdown';

export interface NavPermission {
  permission: string;
  action: 'read' | 'write' | 'manage';
}

export interface NavItem {
  id: string;
  labelKey: string;
  path?: string;
  type: NavItemType;
  children?: NavItem[];
  debugOnly?: boolean;
  requiredPermission?: NavPermission;
}

export interface AppModuleDefinition {
  id: string;
  name: string;
  icon: React.ElementType;
  description: string;
  displayOrder?: number;
  navigation?: NavItem[];
  debugOnly?: boolean;
  sidebarHidden?: boolean;
  requiredPermission?: NavPermission;
}

export function defineAppModule(config: AppModuleDefinition): AppModuleDefinition {
  return config;
}
