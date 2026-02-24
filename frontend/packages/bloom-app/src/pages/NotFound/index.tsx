import { type FC } from 'react';
import { Center, Stack, Title, Text, Button } from '@mantine/core';
import { useNavigate } from 'react-router-dom';

export const NotFoundPage: FC = () => {
    const navigate = useNavigate();

    return (
        <Center h="100vh">
            <Stack align="center" gap="md">
                <Title order={1} size="6rem" c="dimmed">
                    404
                </Title>
                <Title order={2}>Page Not Found</Title>
                <Text c="dimmed" size="lg" ta="center" maw={500}>
                    The page you are looking for does not exist or has been moved.
                </Text>
                <Button variant="subtle" size="md" onClick={() => navigate('/dashboard')}>
                    Go to Dashboard
                </Button>
            </Stack>
        </Center>
    );
};
