import { type FC } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { AuthLayout } from '../layouts/AuthLayout';
import { LoginPage } from '../pages/Login';
import { DashboardPage } from '../pages/Dashboard';
import { NotFoundPage } from '../pages/NotFound';
import { AuthGuard } from './guards';

export const AppRouter: FC = () => {
    return (
        <Routes>
            {/* Public routes */}
            <Route element={<AuthLayout />}>
                <Route path="/login" element={<LoginPage />} />
            </Route>

            {/* Protected routes */}
            <Route element={<AuthGuard />}>
                <Route element={<MainLayout />}>
                    <Route path="/dashboard" element={<DashboardPage />} />
                    {/* Add more routes here:
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          */}
                </Route>
            </Route>

            {/* Redirect & fallback */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<NotFoundPage />} />
        </Routes>
    );
};
