import { type FC, type ReactNode } from 'react';
import { AppShell, Burger, Group, Title, NavLink, ScrollArea } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { LayoutDashboard, FileText, Settings, LogOut } from 'lucide-react';

interface NavItem {
    label: string;
    icon: ReactNode;
    href: string;
    active?: boolean;
}

interface AppLayoutProps {
    children: ReactNode;
    title?: string;
    navItems?: NavItem[];
    onNavigate?: (href: string) => void;
    onLogout?: () => void;
}

const defaultNavItems: NavItem[] = [
    { label: 'Dashboard', icon: <LayoutDashboard size={18} />, href: '/dashboard' },
    { label: 'Reports', icon: <FileText size={18} />, href: '/reports' },
    { label: 'Settings', icon: <Settings size={18} />, href: '/settings' },
];

/**
 * Main application shell — sidebar + header + content area.
 * Uses Mantine AppShell for responsive layout.
 */
export const AppLayout: FC<AppLayoutProps> = ({
    children,
    title = 'Kactus Bloom',
    navItems = defaultNavItems,
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
                </Group>
            </AppShell.Header>

            <AppShell.Navbar p="md">
                <AppShell.Section grow component={ScrollArea}>
                    {navItems.map((item) => (
                        <NavLink
                            key={item.href}
                            label={item.label}
                            leftSection={item.icon}
                            active={item.active}
                            onClick={() => onNavigate?.(item.href)}
                            mb={4}
                        />
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
