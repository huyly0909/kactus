import { CalendarClock } from 'lucide-react';
import { defineAppModule } from '@/lib/module-core';

export default defineAppModule({
  id: 'scheduler',
  name: 'Scheduler',
  labelKey: 'nav.scheduler',
  icon: CalendarClock,
  description: 'Scheduled crawl jobs and the shared sync queue',
  basePath: '/scheduler',
  displayOrder: 45,
  adminOnly: true,
});
