import { Briefcase } from 'lucide-react';
import { defineAppModule } from '@/lib/module-core';

export default defineAppModule({
  id: 'portfolio',
  name: 'Portfolios',
  labelKey: 'nav.portfolios',
  icon: Briefcase,
  description: 'Multi-asset watchlists with scheduled refresh',
  basePath: '/portfolios',
  displayOrder: 20,
  requiresProject: true,
});
