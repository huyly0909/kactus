import { Bell } from 'lucide-react';
import { defineAppModule } from '@/lib/module-core';

export default defineAppModule({
  id: 'notification',
  name: 'Notifications',
  labelKey: 'nav.notifications',
  icon: Bell,
  description: 'Delivery channels for reports and alerts',
  basePath: '/notifications',
  displayOrder: 30,
  requiresProject: true,
});
