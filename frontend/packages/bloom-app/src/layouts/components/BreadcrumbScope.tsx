import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

// BreadcrumbScope lets a detail page push its leaf label (record name) onto the
// breadcrumb without the breadcrumb hook needing to know the record's data
// shape. The page calls useBreadcrumbLeaf('…') inside an effect; useBreadcrumb
// reads it via useBreadcrumbScope().

interface BreadcrumbScopeValue {
  leaf: string | null;
  setLeaf: (s: string | null) => void;
}

const BreadcrumbScopeContext = createContext<BreadcrumbScopeValue>({
  leaf: null,
  setLeaf: () => {},
});

export function BreadcrumbScopeProvider({ children }: { children: ReactNode }) {
  const [leaf, setLeaf] = useState<string | null>(null);
  const value = useMemo(() => ({ leaf, setLeaf }), [leaf]);
  return (
    <BreadcrumbScopeContext.Provider value={value}>{children}</BreadcrumbScopeContext.Provider>
  );
}

export function useBreadcrumbScope(): BreadcrumbScopeValue {
  return useContext(BreadcrumbScopeContext);
}

// Hook for detail pages: registers `label` as the breadcrumb's last crumb while
// mounted, clears on unmount. Null/empty labels are ignored so the breadcrumb
// doesn't drop its last crumb during a record fetch. Two effects on purpose: a
// single effect's cleanup runs on every label change, which would clear the leaf
// mid-fetch — splitting set + clear keeps the clear to actual unmount.
export function useBreadcrumbLeaf(label: string | null) {
  const { setLeaf } = useBreadcrumbScope();
  useEffect(() => {
    if (label) setLeaf(label);
  }, [label, setLeaf]);
  useEffect(() => {
    return () => setLeaf(null);
  }, [setLeaf]);
}
