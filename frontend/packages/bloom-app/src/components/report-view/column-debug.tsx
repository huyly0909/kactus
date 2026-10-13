import { type FC } from 'react';
import { useDebugMode } from '@/hooks/useDebugMode';

// Surfaces a column's raw id under its header — only when debug mode is active
// (superuser + toggle), so report authors can see which data key backs each
// column without shipping the noise to every user.
export const ColumnDebug: FC<{ id: string }> = ({ id }) => {
  const debug = useDebugMode();
  if (!debug) return null;
  return <span className="block text-[10px] font-normal lowercase text-debug">{id}</span>;
};
