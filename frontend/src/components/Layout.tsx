import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function Layout() {
  return (
    <div className="flex min-h-[100dvh] bg-surface-containerLow text-foreground font-sans selection:bg-primary/20 selection:text-primary">
      <Sidebar />
      <main className="flex-1 overflow-x-hidden overflow-y-auto relative">
        <div className="max-w-[1440px] mx-auto p-6 md:p-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
