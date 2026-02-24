import { type FC } from 'react';
import { Center, Stack, Title, Text, Card, ThemeIcon } from '@mantine/core';
import { Sparkles } from 'lucide-react';
import { useAuth } from '@kactus-bloom/ui/hooks';

export const WelcomePage: FC = () => {
  const { user } = useAuth();

  return (
    <Center py="xl">
      <Card shadow="sm" padding="xl" radius="md" withBorder maw={500} w="100%">
        <Stack align="center" gap="lg">
          <ThemeIcon size={64} radius="xl" variant="light" color="indigo">
            <Sparkles size={32} />
          </ThemeIcon>

          <div>
            <Title order={2} ta="center">
              Welcome to Kactus Fin
            </Title>
            <Text c="dimmed" ta="center" mt="xs">
              {user ? `Hello, ${user.name}!` : 'You are logged in.'}
            </Text>
          </div>

          <Text size="sm" c="dimmed" ta="center">
            Your fintech dashboard is ready. Use the sidebar to navigate.
          </Text>
        </Stack>
      </Card>
    </Center>
  );
};
