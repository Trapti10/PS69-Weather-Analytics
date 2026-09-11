import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/layouts/AppLayout'
import { ProtectedRoute } from '@/app/router/ProtectedRoute'
import { RoleRoute } from '@/app/router/RoleRoute'
import { useAuth } from '@/hooks/useAuth'
import { homePathForRole } from '@/utils/roleHome'

import { LoginPage } from '@/pages/auth/LoginPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { NotFoundPage } from '@/pages/shared/NotFoundPage'

import { CitizenDashboardPage } from '@/pages/citizen/CitizenDashboardPage'
import { SubmitReportPage } from '@/pages/citizen/SubmitReportPage'
import { MyReportsPage } from '@/pages/citizen/MyReportsPage'
import { CitizenEventsPage } from '@/pages/citizen/CitizenEventsPage'
import { CitizenMapPage } from '@/pages/citizen/CitizenMapPage'

import { AnalystDashboardPage } from '@/pages/analyst/AnalystDashboardPage'
import { AnalystEventsPage } from '@/pages/analyst/AnalystEventsPage'
import { AnalystAnalyticsPage } from '@/pages/analyst/AnalystAnalyticsPage'
import { AnalystMapPage } from '@/pages/analyst/AnalystMapPage'

import { AdminDashboardPage } from '@/pages/admin/AdminDashboardPage'
import { AdminVerificationQueuePage } from '@/pages/admin/AdminVerificationQueuePage'
import { AdminEvidenceDetailPage } from '@/pages/admin/AdminEvidenceDetailPage'

function RootRedirect() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={homePathForRole(user.role)} replace />
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<RootRedirect />} />

        <Route
          path="/citizen"
          element={
            <RoleRoute allow={['CITIZEN']}>
              <CitizenDashboardPage />
            </RoleRoute>
          }
        />
        <Route
          path="/citizen/report"
          element={
            <RoleRoute allow={['CITIZEN']}>
              <SubmitReportPage />
            </RoleRoute>
          }
        />
        <Route
          path="/citizen/reports"
          element={
            <RoleRoute allow={['CITIZEN']}>
              <MyReportsPage />
            </RoleRoute>
          }
        />
        <Route
          path="/citizen/events"
          element={
            <RoleRoute allow={['CITIZEN']}>
              <CitizenEventsPage />
            </RoleRoute>
          }
        />
        <Route
          path="/citizen/map"
          element={
            <RoleRoute allow={['CITIZEN']}>
              <CitizenMapPage />
            </RoleRoute>
          }
        />

        <Route
          path="/analyst"
          element={
            <RoleRoute allow={['ANALYST']}>
              <AnalystDashboardPage />
            </RoleRoute>
          }
        />
        <Route
          path="/analyst/events"
          element={
            <RoleRoute allow={['ANALYST']}>
              <AnalystEventsPage />
            </RoleRoute>
          }
        />
        <Route
          path="/analyst/analytics"
          element={
            <RoleRoute allow={['ANALYST']}>
              <AnalystAnalyticsPage />
            </RoleRoute>
          }
        />
        <Route
          path="/analyst/map"
          element={
            <RoleRoute allow={['ANALYST']}>
              <AnalystMapPage />
            </RoleRoute>
          }
        />

        <Route
          path="/admin"
          element={
            <RoleRoute allow={['ADMIN']}>
              <AdminDashboardPage />
            </RoleRoute>
          }
        />
        <Route
          path="/admin/verification"
          element={
            <RoleRoute allow={['ADMIN']}>
              <AdminVerificationQueuePage />
            </RoleRoute>
          }
        />
        <Route
          path="/admin/events/:eventId"
          element={
            <RoleRoute allow={['ADMIN']}>
              <AdminEvidenceDetailPage />
            </RoleRoute>
          }
        />

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
