import { lazy, Suspense, Component, type ReactNode } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Spinner, Text } from "@radix-ui/themes";
import { AppLayout } from "./components/ui/AppLayout";

// Pages
import { DashboardPage } from "./pages/DashboardPage";
import { PropertiesPage } from "./pages/PropertiesPage";
import { PropertyDetailPage } from "./pages/PropertyDetailPage";
import { GroupsPage } from "./pages/GroupsPage";
import { GroupDetailPage } from "./pages/GroupDetailPage";
import { ContactsPage } from "./pages/ContactsPage";
import { ContactDetailPage } from "./pages/ContactDetailPage";
import { TransactionsPage } from "./pages/TransactionsPage";
import { TransactionDetailPage } from "./pages/TransactionDetailPage";
import { DealsPage } from "./pages/DealsPage";
import { DealDetailPage } from "./pages/DealDetailPage";
import { ListsPage } from "./pages/ListsPage";
import { ListDetailPage } from "./pages/ListDetailPage";
import { TracePage } from "./pages/TracePage";
import { MonitorPage } from "./pages/MonitorPage";
import { AdminPage } from "./pages/AdminPage";
import { ShowcasePage } from "./pages/ShowcasePage";

const MapPage = lazy(() =>
  import("./pages/MapPage").then((m) => ({ default: m.MapPage }))
);

class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-screen items-center justify-center">
          <div className="text-center">
            <Text size="4" weight="medium" className="block">
              Something went wrong
            </Text>
            <Text size="2" color="gray" className="mt-2 block">
              {this.state.error.message}
            </Text>
            <button
              className="mt-4 text-sm font-medium text-[var(--accent-11)] hover:underline"
              onClick={() => {
                this.setState({ error: null });
                window.location.reload();
              }}
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="properties" element={<PropertiesPage />} />
          <Route path="properties/:id" element={<PropertyDetailPage />} />
          <Route path="groups" element={<GroupsPage />} />
          <Route path="groups/:id" element={<GroupDetailPage />} />
          <Route path="contacts" element={<ContactsPage />} />
          <Route path="contacts/:id" element={<ContactDetailPage />} />
          <Route path="transactions" element={<TransactionsPage />} />
          <Route
            path="transactions/:rtId"
            element={<TransactionDetailPage />}
          />
          <Route path="deals" element={<DealsPage />} />
          <Route path="deals/:id" element={<DealDetailPage />} />
          <Route path="lists" element={<ListsPage />} />
          <Route path="lists/:id" element={<ListDetailPage />} />
          <Route path="trace" element={<TracePage />} />
          <Route path="monitor" element={<MonitorPage />} />
          <Route
            path="map"
            element={
              <Suspense
                fallback={
                  <div className="flex h-96 items-center justify-center">
                    <Spinner size="3" />
                  </div>
                }
              >
                <MapPage />
              </Suspense>
            }
          />
          <Route path="admin" element={<AdminPage />} />
          <Route path="showcase" element={<ShowcasePage />} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
