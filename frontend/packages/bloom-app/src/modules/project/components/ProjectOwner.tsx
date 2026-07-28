import { type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import type { Project } from '@/types/project';

interface ProjectOwnerProps {
  project: Pick<Project, 'has_owner' | 'owner_name' | 'owner_email'>;
  className?: string;
}

/**
 * The owner of a project, or a loud badge when it has none.
 *
 * Every list that shows an owner goes through this, because the naive
 * `owner_name ?? owner_email ?? '—'` cannot tell an unassigned project from an
 * owner whose name is simply blank — it renders both as a dash. A project must
 * always have an owner (`ProjectMember` with `role='owner'`), so losing one is
 * a repairable fault, not an empty cell: see `manage.py fin project
 * repair-owners` and the Assign-owner action on the detail page.
 */
export const ProjectOwner: FC<ProjectOwnerProps> = ({ project, className }) => {
  const { t } = useTranslation();
  if (!project.has_owner) {
    return <Badge variant="destructive">{t('projects.owner_unassigned')}</Badge>;
  }
  return <span className={className}>{project.owner_name ?? project.owner_email}</span>;
};
