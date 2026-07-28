import { describe, it, expect } from 'vitest';
import type { TFunction } from 'i18next';
import {
  PROJECT_CODE_MAX_LENGTH,
  filterAndSortProjects,
  isProjectOwner,
  projectDisplayName,
  projectFormSchema,
  projectMemberCount,
} from './project';
import type { Project } from '@/types/project';

const make = (over: Partial<Project> = {}): Project => ({
  id: '1',
  name: 'First Project',
  code: 'user-526179299714273280',
  status: 'active',
  ...over,
});

describe('projectDisplayName', () => {
  it('pairs the name with the code', () => {
    expect(projectDisplayName(make())).toBe('First Project <user-526179299714273280>');
  });

  it('disambiguates two projects sharing a name', () => {
    const a = projectDisplayName(make({ code: 'user-1' }));
    const b = projectDisplayName(make({ code: 'user-2' }));
    expect(a).not.toBe(b);
  });
});

describe('isProjectOwner', () => {
  it('reads the membership role, not the creator', () => {
    expect(isProjectOwner(make({ my_role: 'owner' }))).toBe(true);
    expect(isProjectOwner(make({ my_role: 'manager' }))).toBe(false);
    // A superuser listing gets no role — that is not ownership.
    expect(isProjectOwner(make({ my_role: null }))).toBe(false);
    expect(isProjectOwner(make())).toBe(false);
  });
});

describe('projectMemberCount', () => {
  it('coerces the FancyInt string to a number', () => {
    expect(projectMemberCount(make({ member_count: '12' }))).toBe(12);
  });

  it('treats a missing count as zero', () => {
    expect(projectMemberCount(make())).toBe(0);
  });
});

describe('projectFormSchema', () => {
  // The factory only needs `t` to look up messages; the key itself is enough
  // to assert *which* rule fired.
  const schema = projectFormSchema(((key: string) => key) as unknown as TFunction);
  const values = { name: 'Team', code: 'team-x', description: '' };

  it('accepts a slug code', () => {
    expect(schema.safeParse(values).success).toBe(true);
  });

  it('rejects a code longer than the column', () => {
    const result = schema.safeParse({ ...values, code: 'x'.repeat(PROJECT_CODE_MAX_LENGTH + 1) });
    expect(result.success).toBe(false);
    // Caught client-side so the request the DB would truncate is never sent.
    expect(result.error?.issues[0].message).toBe('projects.code_max');
  });

  it('rejects a non-slug code', () => {
    expect(schema.safeParse({ ...values, code: 'Team X' }).success).toBe(false);
  });

  it('requires a name', () => {
    expect(schema.safeParse({ ...values, name: '  ' }).success).toBe(false);
  });
});

describe('filterAndSortProjects', () => {
  const rows = [
    make({ id: 'a', create_time: '2026-01-01T00:00:00Z' }),
    make({ id: 'b', create_time: '2026-03-01T00:00:00Z' }),
    make({ id: 'c', status: 'archived', create_time: '2026-02-01T00:00:00Z' }),
  ];

  it('hides archived projects by default', () => {
    expect(filterAndSortProjects(rows, 'active').map((p) => p.id)).toEqual(['b', 'a']);
  });

  it('shows only archived when asked', () => {
    expect(filterAndSortProjects(rows, 'archived').map((p) => p.id)).toEqual(['c']);
  });

  it('orders newest first', () => {
    expect(filterAndSortProjects(rows, 'all').map((p) => p.id)).toEqual(['b', 'c', 'a']);
  });

  it('does not mutate the input', () => {
    const input = [...rows];
    filterAndSortProjects(input, 'all');
    expect(input.map((p) => p.id)).toEqual(['a', 'b', 'c']);
  });

  it('tolerates a missing create_time', () => {
    const withNull = [make({ id: 'x' }), make({ id: 'y', create_time: '2026-01-01T00:00:00Z' })];
    expect(filterAndSortProjects(withNull, 'all').map((p) => p.id)).toEqual(['y', 'x']);
  });
});
