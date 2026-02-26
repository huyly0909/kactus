import { type FC } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from '../layouts/MainLayout';
import { AuthLayout } from '../layouts/AuthLayout';
import { LoginPage } from '../pages/Login';
import { WelcomePage } from '../pages/Welcome';
import { DashboardPage } from '../pages/Dashboard';
import { NotFoundPage } from '../pages/NotFound';
import { ProjectSelectPage } from '../pages/ProjectSelect';
import { AdminLayout } from '../pages/Admin';
import { AdminUsersPage } from '../pages/Admin/Users';
import { AdminProjectsPage } from '../pages/Admin/Projects';
import { AdminAuthorizationPage } from '../pages/Admin/Authorization';
import { AuthGuard } from './guards';
import { AdminGuard } from './adminGuard';
import { ProjectGuard } from './projectGuard';

export const AppRouter: FC = () => {
  return (
    <Routes>
      {/* Public routes */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

      {/* Protected routes — require auth */}
      <Route element={<AuthGuard />}>
        {/* Admin routes — separate layout, no project needed */}
        <Route element={<AdminGuard />}>
          <Route element={<AdminLayout />}>
            <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
            <Route path="/admin/users" element={<AdminUsersPage />} />
            <Route path="/admin/projects" element={<AdminProjectsPage />} />
            <Route path="/admin/authorization" element={<AdminAuthorizationPage />} />
          </Route>
        </Route>

        {/* User routes — own layout with project context */}
        <Route element={<MainLayout />}>
          <Route path="/select-project" element={<ProjectSelectPage />} />

          <Route element={<ProjectGuard />}>
            <Route path="/welcome" element={<WelcomePage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            {/* Add more project-scoped routes here */}
          </Route>
        </Route>
      </Route>

      {/* Redirect & fallback */}
      <Route path="/" element={<Navigate to="/welcome" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
};
