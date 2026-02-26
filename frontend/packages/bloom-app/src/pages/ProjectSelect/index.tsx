import { type FC, useEffect, useState } from 'react';
import {
  Center,
  Stack,
  Title,
  Text,
  Card,
  Group,
  Badge,
  SimpleGrid,
  Loader,
  Button,
  Modal,
  TextInput,
  Textarea,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { FolderOpen, FolderPlus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { projectService } from '@kactus-bloom/ui/services';
import { useProjectStore } from '@kactus-bloom/ui/stores';
import type { Project } from '@kactus-bloom/ui/types';

export const ProjectSelectPage: FC = () => {
  const navigate = useNavigate();
  const { setProject } = useProjectStore();
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false);

  // Create form state
  const [projectName, setProjectName] = useState('');
  const [projectCode, setProjectCode] = useState('');
  const [projectDescription, setProjectDescription] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  const loadProjects = async () => {
    try {
      const data = await projectService.getProjects();
      setProjects(data.items);
    } catch {
      setProjects([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const handleSelect = (project: Project) => {
    setProject(project);
    navigate('/dashboard');
  };

  const handleCreate = async () => {
    if (!projectName.trim() || !projectCode.trim()) return;

    setIsCreating(true);
    try {
      const project = await projectService.createProject({
        name: projectName,
        code: projectCode,
        description: projectDescription || undefined,
      });
      notifications.show({ title: 'Success', message: 'Project created', color: 'green' });
      closeCreate();
      setProjectName('');
      setProjectCode('');
      setProjectDescription('');
      setProject(project);
      navigate('/dashboard');
    } catch {
      notifications.show({ title: 'Error', message: 'Failed to create project', color: 'red' });
    } finally {
      setIsCreating(false);
    }
  };

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader size="lg" />
      </Center>
    );
  }

  return (
    <Stack align="center" gap="xl" mt="xl">
      <Stack align="center" gap="xs">
        <FolderOpen size={48} strokeWidth={1.5} color="var(--mantine-color-blue-6)" />
        <Title order={2}>Select a Project</Title>
        <Text c="dimmed" ta="center" maw={400}>
          Choose a project to continue. All features require a project context.
        </Text>
      </Stack>

      {projects.length === 0 ? (
        <Stack align="center" gap="md">
          <Text c="dimmed" size="lg">
            You are not a member of any projects yet.
          </Text>
          <Button leftSection={<FolderPlus size={18} />} size="md" onClick={openCreate}>
            Create Project
          </Button>
        </Stack>
      ) : (
        <>
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md" w="100%" maw={600}>
            {projects.map((project) => (
              <Card
                key={project.id}
                shadow="sm"
                padding="lg"
                radius="md"
                withBorder
                style={{ cursor: 'pointer' }}
                onClick={() => handleSelect(project)}
              >
                <Group justify="space-between" mb="xs">
                  <Text fw={600} size="lg">
                    {project.name}
                  </Text>
                  <Badge color="blue" variant="light">
                    {project.code}
                  </Badge>
                </Group>
                {project.description && (
                  <Text size="sm" c="dimmed" lineClamp={2}>
                    {project.description}
                  </Text>
                )}
              </Card>
            ))}
          </SimpleGrid>
          <Button leftSection={<FolderPlus size={16} />} variant="light" onClick={openCreate}>
            Create New Project
          </Button>
        </>
      )}

      {/* Create Project Modal */}
      <Modal opened={createOpened} onClose={closeCreate} title="Create Project">
        <Stack gap="md">
          <TextInput
            label="Project Name"
            placeholder="My Project"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            required
          />
          <TextInput
            label="Project Code"
            placeholder="my-project"
            value={projectCode}
            onChange={(e) => setProjectCode(e.target.value)}
            required
          />
          <Textarea
            label="Description"
            placeholder="Optional project description"
            value={projectDescription}
            onChange={(e) => setProjectDescription(e.target.value)}
            minRows={3}
          />
          <Button onClick={handleCreate} loading={isCreating}>
            Create
          </Button>
        </Stack>
      </Modal>
    </Stack>
  );
};
