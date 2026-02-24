import { type FC } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
    Card,
    Title,
    Text,
    TextInput,
    PasswordInput,
    Button,
    Stack,
    Alert,
} from '@mantine/core';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { AlertCircle } from 'lucide-react';
import { useState } from 'react';
import { loginSchema, type LoginFormData } from '@kactus-bloom/ui/utils';
import { useAuth } from '@kactus-bloom/ui/hooks';

export const LoginPage: FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { login } = useAuth();
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/dashboard';

    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm<LoginFormData>({
        resolver: zodResolver(loginSchema),
    });

    const onSubmit = async (data: LoginFormData) => {
        setError(null);
        setLoading(true);
        try {
            await login(data);
            navigate(from, { replace: true });
        } catch {
            setError('Invalid email or password. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card shadow="md" padding="xl" radius="md" withBorder>
            <Stack gap="md">
                <div>
                    <Title order={2} ta="center">
                        Kactus Bloom
                    </Title>
                    <Text c="dimmed" size="sm" ta="center" mt={4}>
                        Sign in to your fintech dashboard
                    </Text>
                </div>

                {error && (
                    <Alert icon={<AlertCircle size={16} />} color="red" variant="light">
                        {error}
                    </Alert>
                )}

                <form onSubmit={handleSubmit(onSubmit)}>
                    <Stack gap="sm">
                        <TextInput
                            label="Email"
                            placeholder="you@company.com"
                            {...register('email')}
                            error={errors.email?.message}
                        />
                        <PasswordInput
                            label="Password"
                            placeholder="Your password"
                            {...register('password')}
                            error={errors.password?.message}
                        />
                        <Button type="submit" fullWidth loading={loading} mt="sm">
                            Sign In
                        </Button>
                    </Stack>
                </form>
            </Stack>
        </Card>
    );
};
