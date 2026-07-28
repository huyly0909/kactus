import type { FC, ReactElement } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Skeleton } from '@/components/ui/skeleton';
import { useProjectStore } from '@/store/projectStore';

interface Props {
  children: ReactElement;
}

/**
 * Gate for routes whose data is project-scoped. Without the `kactus_project_id`
 * cookie the backend answers those endpoints with 403 "No project selected", so
 * the page would render as a wall of empty widgets with no hint why — send the
 * user to the picker instead.
 *
 * It waits for `hydrated` first. The store is not persisted, so `currentProject`
 * is `null` on every page load until `hydrateActiveProject` resolves it — and
 * `setUser` flips the auth loading flag *synchronously*, so the router mounts
 * mid-flight. Redirecting on that initial `null` is what bounced every hard
 * refresh of a project route to `/projects`.
 *
 * The target route travels along in `location.state.from`, so the picker can
 * return the user where they were instead of dumping them on the project list.
 */
export const RequireProject: FC<Props> = ({ children }) => {
  const location = useLocation();
  const hydrated = useProjectStore((s) => s.hydrated);
  const hasProject = useProjectStore((s) => s.currentProject !== null);

  if (!hydrated) return <Skeleton className="m-6 h-64 md:m-8" />;
  return hasProject ? children : <Navigate to="/projects" state={{ from: location }} replace />;
};
