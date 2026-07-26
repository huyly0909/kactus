import { useEffect, useRef } from 'react';
import { Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

// Catch-all (`path="*"`). An unknown/typo'd URL gets a one-time toast and
// redirects home (a real module route → never re-hits `*`). Replaces the old
// silent "Page not found" div.
export function NotFoundRedirect() {
  const { t } = useTranslation();
  const toastedRef = useRef(false);

  useEffect(() => {
    if (!toastedRef.current) {
      toastedRef.current = true;
      toast.error(t('nav.route_not_found'));
    }
  }, [t]);

  return <Navigate to="/" replace />;
}
