import { type FC, type ReactNode } from 'react';
import { AppShell, Burger, Group, Title, NavLink, ScrollArea, Divider, Text } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { LogOut } from 'lucide-react';

interface NavSection {
  label?: string;
  items: NavItem[];
}

interface NavItem {
  label: string;
  icon: ReactNode;
  href: string;
}

interface AppLayoutProps {
  children: ReactNode;
  /** Title shown in the header. */
  title?: string;
  /** Sections of nav items to display in the sidebar. */
  navSections: NavSection[];
  /** Current pathname for active-item highlighting. */
  currentPath?: string;
  /** Optional extra content in the header (right side). */
  headerRight?: ReactNode;
  onNavigate?: (href: string) => void;
  onLogout?: () => void;
}

/**
 * Generic application shell — sidebar + header + content area.
 * Each layout (Admin, User) composes this with its own nav sections.
 */
export const AppLayout: FC<AppLayoutProps> = ({
  children,
  title = 'Kactus Bloom',
  navSections,
  currentPath = '',
  headerRight,
  onNavigate,
  onLogout,
}) => {
  const [opened, { toggle }] = useDisclosure();

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 250, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={3}>{title}</Title>
          </Group>
          {headerRight}
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <AppShell.Section grow component={ScrollArea}>
          {navSections.map((section, idx) => (
            <div key={section.label ?? idx}>
              {idx > 0 && <Divider my="sm" />}
              {section.label && (
                <Text size="xs" c="dimmed" fw={600} tt="uppercase" mb={4} px="sm">
                  {section.label}
                </Text>
              )}
              {section.items.map((item) => (
                <NavLink
                  key={item.href}
                  label={item.label}
                  leftSection={item.icon}
                  active={currentPath === item.href}
                  onClick={() => onNavigate?.(item.href)}
                  mb={4}
                />
              ))}
            </div>
          ))}
        </AppShell.Section>

        <AppShell.Section>
          <NavLink
            label="Logout"
            leftSection={<LogOut size={18} />}
            onClick={onLogout}
            color="red"
          />
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main>{children}</AppShell.Main>
    </AppShell>
  );
};
