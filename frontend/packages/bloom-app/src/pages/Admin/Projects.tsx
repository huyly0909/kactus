import { type FC, useEffect, useState } from 'react';
import { Title, Stack, Table, Badge, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { adminService } from '@kactus-bloom/ui/services';
import type { Project } from '@kactus-bloom/ui/types';

export const AdminProjectsPage: FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadProjects = async () => {
      try {
        const data = await adminService.getAllProjects();
        setProjects(data.items);
      } catch {
        notifications.show({ title: 'Error', message: 'Failed to load projects', color: 'red' });
      } finally {
        setIsLoading(false);
      }
    };
    loadProjects();
  }, []);

  return (
    <Stack gap="lg">
      <Title order={3}>All Projects</Title>

      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Name</Table.Th>
            <Table.Th>Code</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Description</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {isLoading ? (
            <Table.Tr>
              <Table.Td colSpan={4}>
                <Text ta="center" c="dimmed">
                  Loading...
                </Text>
              </Table.Td>
            </Table.Tr>
          ) : projects.length === 0 ? (
            <Table.Tr>
              <Table.Td colSpan={4}>
                <Text ta="center" c="dimmed">
                  No projects found
                </Text>
              </Table.Td>
            </Table.Tr>
          ) : (
            projects.map((project) => (
              <Table.Tr key={project.id}>
                <Table.Td fw={500}>{project.name}</Table.Td>
                <Table.Td>
                  <Badge color="blue" variant="light">
                    {project.code}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Badge color={project.status === 'active' ? 'green' : 'gray'}>
                    {project.status}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed" lineClamp={1}>
                    {project.description || '—'}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ))
          )}
        </Table.Tbody>
      </Table>
    </Stack>
  );
};
