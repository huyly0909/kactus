import { type FC, useEffect, useState } from 'react';
import {
  Title,
  Stack,
  Table,
  Button,
  Group,
  Modal,
  TextInput,
  Checkbox,
  Badge,
  Text,
  ActionIcon,
  CopyButton,
  Tooltip,
  Menu,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { UserPlus, KeyRound, UserX, Copy, Check, Shield, ShieldOff } from 'lucide-react';
import { adminService } from '@kactus-bloom/ui/services';

interface UserInfo {
  id: string;
  email: string;
  name: string;
  status: string;
  is_superuser: boolean;
}

export const AdminUsersPage: FC = () => {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);
  const [newPassword, setNewPassword] = useState<string | null>(null);
  const [passwordModalOpened, { open: openPasswordModal, close: closePasswordModal }] =
    useDisclosure(false);

  // Form state
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [isSuperuser, setIsSuperuser] = useState(false);

  const loadUsers = async () => {
    try {
      const data = await adminService.getUsers();
      setUsers(data.items);
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to load users', color: 'red' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleCreate = async () => {
    try {
      await adminService.createUser({ email, name, password, is_superuser: isSuperuser });
      notifications.show({ title: 'Success', message: 'User created', color: 'green' });
      closeCreate();
      setEmail('');
      setName('');
      setPassword('');
      setIsSuperuser(false);
      loadUsers();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to create user', color: 'red' });
    }
  };

  const handleResetPassword = async (userId: string) => {
    try {
      const data = await adminService.resetPassword(userId);
      setNewPassword(data.new_password);
      openPasswordModal();
      notifications.show({ title: 'Success', message: 'Password reset', color: 'green' });
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to reset password', color: 'red' });
    }
  };

  const handleDeactivate = async (userId: string) => {
    try {
      await adminService.deactivateUser(userId);
      notifications.show({ title: 'Success', message: 'User deactivated', color: 'green' });
      loadUsers();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to deactivate user', color: 'red' });
    }
  };

  const handleToggleRole = async (user: UserInfo) => {
    const newRole = !user.is_superuser;
    try {
      await adminService.updateUserRole(user.id, { is_superuser: newRole });
      notifications.show({
        title: 'Success',
        message: `${user.name} is now ${newRole ? 'an Admin' : 'a regular user'}`,
        color: 'green',
      });
      loadUsers();
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to update role', color: 'red' });
    }
  };

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={3}>User Management</Title>
        <Button leftSection={<UserPlus size={16} />} onClick={openCreate}>
          Create User
        </Button>
      </Group>

      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Name</Table.Th>
            <Table.Th>Email</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Role</Table.Th>
            <Table.Th>Actions</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {isLoading ? (
            <Table.Tr>
              <Table.Td colSpan={5}>
                <Text ta="center" c="dimmed">
                  Loading...
                </Text>
              </Table.Td>
            </Table.Tr>
          ) : users.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={5}>
                <Text ta="center" c="dimmed">
                  No users found
                </Text>
              </Table.Td>
            </Table.Tr>
          ) : (
            users.map((user) => (
              <Table.Tr key={user.id}>
                <Table.Td>{user.name}</Table.Td>
                <Table.Td>{user.email}</Table.Td>
                <Table.Td>
                  <Badge color={user.status === 'active' ? 'green' : 'gray'}>{user.status}</Badge>
                </Table.Td>
                <Table.Td>
                  <Menu shadow="md" width={200}>
                    <Menu.Target>
                      <Badge
                        color={user.is_superuser ? 'red' : 'blue'}
                        variant="light"
                        style={{ cursor: 'pointer' }}
                      >
                        {user.is_superuser ? 'Admin' : 'User'}
                      </Badge>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Label>Change Role</Menu.Label>
                      <Menu.Item
                        leftSection={
                          user.is_superuser ? <ShieldOff size={14} /> : <Shield size={14} />
                        }
                        color={user.is_superuser ? 'blue' : 'red'}
                        onClick={() => handleToggleRole(user)}
                      >
                        {user.is_superuser ? 'Demote to User' : 'Promote to Admin'}
                      </Menu.Item>
                    </Menu.Dropdown>
                  </Menu>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    <Tooltip label="Reset Password">
                      <ActionIcon
                        variant="subtle"
                        color="blue"
                        onClick={() => handleResetPassword(user.id)}
                      >
                        <KeyRound size={16} />
                      </ActionIcon>
                    </Tooltip>
                    {user.status === 'active' && (
                      <Tooltip label="Deactivate">
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          onClick={() => handleDeactivate(user.id)}
                        >
                          <UserX size={16} />
                        </ActionIcon>
                      </Tooltip>
                    )}
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))
          )}
        </Table.Tbody>
      </Table>

      {/* Create User Modal */}
      <Modal opened={createOpened} onClose={closeCreate} title="Create User">
        <Stack gap="md">
          <TextInput
            label="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <TextInput label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
          <TextInput
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Checkbox
            label="Admin (Superuser)"
            checked={isSuperuser}
            onChange={(e) => setIsSuperuser(e.currentTarget.checked)}
          />
          <Button onClick={handleCreate}>Create</Button>
        </Stack>
      </Modal>

      {/* Password Reset Modal */}
      <Modal
        opened={passwordModalOpened}
        onClose={() => {
          closePasswordModal();
          setNewPassword(null);
        }}
        title="Password Reset"
      >
        <Stack gap="md">
          <Text>New password generated. Please copy and share securely:</Text>
          <Group gap="sm">
            <TextInput value={newPassword || ''} readOnly style={{ flex: 1 }} />
            <CopyButton value={newPassword || ''} timeout={2000}>
              {({ copied, copy }) => (
                <Tooltip label={copied ? 'Copied' : 'Copy'}>
                  <ActionIcon color={copied ? 'teal' : 'gray'} variant="subtle" onClick={copy}>
                    {copied ? <Check size={16} /> : <Copy size={16} />}
                  </ActionIcon>
                </Tooltip>
              )}
            </CopyButton>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
};
