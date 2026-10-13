import { LayoutDashboard } from 'lucide-react';
import { defineAppModule } from '@/lib/module-core';

export default defineAppModule({
  id: 'dashboard',
  name: 'Dashboard',
  labelKey: 'nav.dashboard',
  icon: LayoutDashboard,
  description: 'Overview of watchlists and notification channels',
  basePath: '/',
  displayOrder: 10,
  requiresProject: true,
});
