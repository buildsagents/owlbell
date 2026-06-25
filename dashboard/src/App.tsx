import { RouterProvider } from "react-router-dom";
import { router } from "@/app/routes";
import { AppProviders } from "@/app/providers";
import { ErrorBoundary } from "@/app/error-boundary";

export default function App() {
  return (
    <ErrorBoundary>
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    </ErrorBoundary>
  );
}
