import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import GlobalHeader from "./GlobalHeader";

export default function AppLayout() {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <main className="ml-60 min-h-screen bg-b-surface1">
        <GlobalHeader />
        <Outlet />
      </main>
    </div>
  );
}
