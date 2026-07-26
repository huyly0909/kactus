import { FolderKanban } from 'lucide-react';
import { defineAppModule } from '@/lib/module-core';

export default defineAppModule({
  id: 'projects',
  name: 'Projects',
  labelKey: 'nav.projects',
  icon: FolderKanban,
  description: 'Projects you belong to — select one to scope your data, invite members',
  basePath: '/projects',
  displayOrder: 15,
});
