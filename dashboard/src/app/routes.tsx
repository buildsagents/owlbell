import { lazy, Suspense } from "react";
import {
  createBrowserRouter,
  Navigate,
  Outlet,
} from "react-router-dom";
import { AppLayout } from "@/app/layout";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { ProtectedRoute } from "@/components/shared/protected-route";

const LoginPage = lazy(() => import("@/pages/auth/login"));
const SignupPage = lazy(() => import("@/pages/auth/signup"));
const ForgotPasswordPage = lazy(() => import("@/pages/auth/forgot-password"));
const ResetPasswordPage = lazy(() => import("@/pages/auth/reset-password"));
const MfaSetupPage = lazy(() => import("@/pages/auth/mfa-setup"));

const DashboardPage = lazy(() => import("@/pages/dashboard/overview"));
const CallsListPage = lazy(() => import("@/pages/calls/index"));
const CallDetailPage = lazy(() => import("@/pages/calls/[callId]"));
const LiveCallsPage = lazy(() => import("@/pages/calls/live"));
const AnalyticsPage = lazy(() => import("@/pages/analytics/index"));
const MessagesPage = lazy(() => import("@/pages/messages/index"));
const AppointmentsPage = lazy(() => import("@/pages/appointments/index"));
const AiPersonalityPage = lazy(() => import("@/pages/settings/ai-personality"));
const BusinessHoursPage = lazy(() => import("@/pages/settings/business-hours"));
const KnowledgeBasePage = lazy(() => import("@/pages/settings/knowledge-base"));
const IntegrationsPage = lazy(() => import("@/pages/settings/integrations"));
const NotificationSettingsPage = lazy(() => import("@/pages/settings/notifications"));
const TeamPage = lazy(() => import("@/pages/team/index"));
const BillingPage = lazy(() => import("@/pages/billing/index"));
const AgencyOverviewPage = lazy(() => import("@/pages/agency/index"));
const AgencyClientsPage = lazy(() => import("@/pages/agency/clients"));
const AgencyProvisionPage = lazy(() => import("@/pages/agency/provision"));
const AgencyClientDetailPage = lazy(() => import("@/pages/agency/client/[clientId]"));
const AgencyOnboardingPage = lazy(() => import("@/pages/agency/onboarding"));
const OutreachPage = lazy(() => import("@/pages/outreach/index"));

function PageLoader() {
  return (
    <div className="flex h-[60vh] items-center justify-center">
      <LoadingSpinner size="lg" />
    </div>
  );
}

export const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <Navigate to="/dashboard" replace />,
    },
    {
      path: "/login",
      element: (
        <Suspense fallback={<PageLoader />}>
          <LoginPage />
        </Suspense>
      ),
    },
    {
      path: "/signup",
      element: (
        <Suspense fallback={<PageLoader />}>
          <SignupPage />
        </Suspense>
      ),
    },
    {
      path: "/forgot-password",
      element: (
        <Suspense fallback={<PageLoader />}>
          <ForgotPasswordPage />
        </Suspense>
      ),
    },
    {
      path: "/reset-password",
      element: (
        <Suspense fallback={<PageLoader />}>
          <ResetPasswordPage />
        </Suspense>
      ),
    },
    {
      path: "/mfa-setup",
      element: (
        <Suspense fallback={<PageLoader />}>
          <MfaSetupPage />
        </Suspense>
      ),
    },
    {
      path: "/",
      element: (
        <ProtectedRoute>
          <AppLayout>
            <Suspense fallback={<PageLoader />}>
              <Outlet />
            </Suspense>
          </AppLayout>
        </ProtectedRoute>
      ),
      children: [
        {
          path: "dashboard",
          element: <DashboardPage />,
        },
        {
          path: "calls",
          children: [
            { index: true, element: <CallsListPage /> },
            { path: "live", element: <LiveCallsPage /> },
            { path: ":callId", element: <CallDetailPage /> },
          ],
        },
        {
          path: "analytics",
          element: <AnalyticsPage />,
        },
        {
          path: "messages",
          element: <MessagesPage />,
        },
        {
          path: "appointments",
          element: <AppointmentsPage />,
        },
        {
          path: "settings",
          children: [
            { path: "ai-personality", element: <AiPersonalityPage /> },
            { path: "business-hours", element: <BusinessHoursPage /> },
            { path: "knowledge-base", element: <KnowledgeBasePage /> },
            { path: "integrations", element: <IntegrationsPage /> },
            { path: "notifications", element: <NotificationSettingsPage /> },
            { index: true, element: <Navigate to="ai-personality" replace /> },
          ],
        },
        {
          path: "team",
          element: <TeamPage />,
        },
        {
          path: "billing",
          element: <BillingPage />,
        },
        {
          path: "agency",
          children: [
            { index: true, element: <AgencyOverviewPage /> },
            { path: "clients", element: <AgencyClientsPage /> },
            { path: "provision", element: <AgencyProvisionPage /> },
            { path: "client/:clientId", element: <AgencyClientDetailPage /> },
            { path: "onboarding", element: <AgencyOnboardingPage /> },
          ],
        },
        {
          path: "outreach",
          element: <OutreachPage />,
        },
      ],
    },
    {
      path: "*",
      element: (
        <div className="flex h-screen items-center justify-center">
          <div className="text-center">
            <h1 className="text-4xl font-bold">404</h1>
            <p className="text-muted-foreground mt-2">Page not found</p>
          </div>
        </div>
      ),
    },
  ],
  { basename: "/app" },
);
