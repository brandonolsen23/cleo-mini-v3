import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

export function AppLayout() {
  return (
    <div className="app-layout">
      <Sidebar />
      <Header />
      <main className="app-main bg-[var(--color-background)]">
        <div className="mx-auto max-w-[72rem] px-6 pt-6 pb-16">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
