import { type FC, useEffect, useState } from 'react';
import { Title, Stack, Text, Table, Badge, Loader, Center } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { adminService } from '@kactus-bloom/ui/services';

interface PermissionItem {
  permission: string;
  act: string;
}

type AuthorizationData = Record<string, PermissionItem[]>;

const ROLE_COLORS: Record<string, string> = {
  admin: 'red',
  owner: 'orange',
  manager: 'yellow',
  member: 'blue',
};

export const AdminAuthorizationPage: FC = () => {
  const [data, setData] = useState<AuthorizationData>({});
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const result = await adminService.getAuthorization();
        setData(result);
      } catch {
        notifications.show({
          title: 'Error',
          message: 'Failed to load authorization data',
          color: 'red',
        });
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, []);

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader size="md" />
      </Center>
    );
  }

  const roles = Object.entries(data);

  return (
    <Stack gap="lg">
      <Title order={3}>Authorization</Title>
      <Text c="dimmed">Default role-permission mapping for all projects.</Text>

      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Role</Table.Th>
            <Table.Th>Permissions</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {roles.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={2}>
                <Text ta="center" c="dimmed">
                  No roles configured.
                </Text>
              </Table.Td>
            </Table.Tr>
          ) : (
            roles.map(([role, permissions]) => (
              <Table.Tr key={role}>
                <Table.Td>
                  <Badge color={ROLE_COLORS[role] || 'gray'} variant="light" size="lg">
                    {role}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  {permissions.map((perm) => (
                    <Badge key={`${perm.permission}:${perm.act}`} variant="outline" mr={4} mb={4}>
                      {perm.permission}:{perm.act}
                    </Badge>
                  ))}
                </Table.Td>
              </Table.Tr>
            ))
          )}
        </Table.Tbody>
      </Table>
    </Stack>
  );
};
