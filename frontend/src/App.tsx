import { Component, lazy, Suspense } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import TransactionsPage from "./components/transactions/TransactionsPage";
import TransactionDetailPage from "./components/transactions/TransactionDetailPage";
import DashboardPage from "./components/dashboard/DashboardPage";
import AdminPage from "./components/admin/AdminPage";
import MonitorPage from "./components/monitor/MonitorPage";
import TracePage from "./components/trace/TracePage";
import ParcelsPage from "./components/parcels/ParcelsPage";
import ParcelDetailPage from "./components/parcels/ParcelDetailPage";

const MapPage = lazy(() => import("./components/map/MapPage"));

class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled error:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="max-w-md text-center">
            <h2 className="text-lg font-semibold text-red-600 mb-2">Something went wrong</h2>
            <p className="text-sm text-gray-600 mb-4">{this.state.error?.message}</p>
            <button
              className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded"
              onClick={() => window.location.reload()}
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
          <Route path="parcels" element={<ParcelsPage />} />
          <Route path="parcels/:arn" element={<ParcelDetailPage />} />
          <Route path="transactions" element={<TransactionsPage />} />
          <Route path="transactions/:rtId" element={<TransactionDetailPage />} />
          {/* Legacy property URLs redirect to parcels */}
          <Route path="properties/:propId" element={<Navigate to="/parcels" replace />} />
          <Route path="trace" element={<TracePage />} />
          <Route path="monitor" element={<MonitorPage />} />
          <Route path="admin" element={<AdminPage />} />
          <Route path="map" element={<Suspense fallback={<div className="flex-1 flex items-center justify-center"><p className="text-sm text-gray-500">Loading map...</p></div>}><MapPage /></Suspense>} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
