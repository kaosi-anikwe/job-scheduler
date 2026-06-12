import { Outlet } from 'react-router';
import { Sidebar } from '../components/Sidebar';

export function Layout() {
  return (
    <div className="h-screen overflow-hidden flex">
      <Sidebar />
      <main className="flex-1 bg-base-100 overflow-y-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
