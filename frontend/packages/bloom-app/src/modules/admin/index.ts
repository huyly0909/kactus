import { ShieldCheck } from 'lucide-react';
import { defineAppModule } from '@/lib/module-core';

export default defineAppModule({
  id: 'admin',
  name: 'Admin',
  labelKey: 'nav.admin',
  icon: ShieldCheck,
  description: 'User, project and authorization administration',
  basePath: '/admin',
  displayOrder: 90,
  adminOnly: true,
  navigation: [
    {
      id: 'admin-users',
      type: 'link',
      labelKey: 'nav.users',
      path: '/admin/users',
      adminOnly: true,
    },
    {
      id: 'admin-projects',
      type: 'link',
      labelKey: 'nav.projects',
      path: '/admin/projects',
      adminOnly: true,
    },
    {
      id: 'admin-authorization',
      type: 'link',
      labelKey: 'nav.authorization',
      path: '/admin/authorization',
      adminOnly: true,
    },
  ],
});
