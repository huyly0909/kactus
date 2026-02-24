import { type FC } from 'react';
import { Outlet } from 'react-router-dom';
import { Center, Container } from '@mantine/core';

/**
 * Auth layout — centered container for login/register pages.
 */
export const AuthLayout: FC = () => {
    return (
        <Center h="100vh" bg="gray.0">
            <Container size="xs" w="100%">
                <Outlet />
            </Container>
        </Center>
    );
};
