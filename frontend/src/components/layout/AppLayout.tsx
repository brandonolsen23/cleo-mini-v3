import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import GlobalHeader from "./GlobalHeader";

export default function AppLayout() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#eef2fb] via-[#f3eef8] to-[#f8eef3]">
      <Sidebar />
      <main className="ml-60 min-h-screen">
        <GlobalHeader />
        <Outlet />
      </main>
    </div>
  );
}
