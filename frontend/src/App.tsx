import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import TransactionsPage from "./components/transactions/TransactionsPage";
import TransactionDetailPage from "./components/transactions/TransactionDetailPage";
import PropertiesPage from "./components/properties/PropertiesPage";
import PropertyDetailPage from "./components/properties/PropertyDetailPage";
import PartiesPage from "./components/parties/PartiesPage";
import PartyDetailPage from "./components/parties/PartyDetailPage";
import ContactsPage from "./components/contacts/ContactsPage";
import ContactDetailPage from "./components/contacts/ContactDetailPage";
import BrandsPage from "./components/brands/BrandsPage";
import DashboardPage from "./components/dashboard/DashboardPage";
import AdminPage from "./components/admin/AdminPage";
import CrmContactsPage from "./components/crm/CrmContactsPage";
import CrmContactDetailPage from "./components/crm/CrmContactDetailPage";
import DealsPage from "./components/crm/DealsPage";
import DealDetailPage from "./components/crm/DealDetailPage";
import OperatorsPage from "./components/operators/OperatorsPage";
import OperatorDetailPage from "./components/operators/OperatorDetailPage";
import OutreachListsPage from "./components/outreach/OutreachListsPage";
import OutreachBuilderPage from "./components/outreach/OutreachBuilderPage";
import OutreachListDetailPage from "./components/outreach/OutreachListDetailPage";

const MapPage = lazy(() => import("./components/map/MapPage"));

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="transactions/:rtId" element={<TransactionDetailPage />} />
        <Route path="properties" element={<PropertiesPage />} />
        <Route path="properties/:propId" element={<PropertyDetailPage />} />
        <Route path="parties" element={<PartiesPage />} />
        <Route path="parties/:groupId" element={<PartyDetailPage />} />
        <Route path="contacts" element={<ContactsPage />} />
        <Route path="contacts/:contactId" element={<ContactDetailPage />} />
        <Route path="crm/contacts" element={<CrmContactsPage />} />
        <Route path="crm/contacts/:crmId" element={<CrmContactDetailPage />} />
        <Route path="crm/deals" element={<DealsPage />} />
        <Route path="crm/deals/:dealId" element={<DealDetailPage />} />
        <Route path="operators" element={<OperatorsPage />} />
        <Route path="operators/:opId" element={<OperatorDetailPage />} />
        <Route path="outreach" element={<OutreachListsPage />} />
        <Route path="outreach/new" element={<OutreachBuilderPage />} />
        <Route path="outreach/:listId" element={<OutreachListDetailPage />} />
        <Route path="brands" element={<BrandsPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="map" element={<Suspense fallback={<div className="flex-1 flex items-center justify-center"><p className="text-sm text-gray-500">Loading map...</p></div>}><MapPage /></Suspense>} />
      </Route>
    </Routes>
  );
}
