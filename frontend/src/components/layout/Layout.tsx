/**
 * Layout.tsx — app shell used by App.tsx as the parent <Route element>.
 * Renders the persistent Sidebar on the left and the current page via <Outlet> on the right.
 */
import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../Sidebar';

const Layout: React.FC = () => (
  <div className="flex h-screen overflow-hidden bg-gnosis-bg text-gnosis-fg">
    <Sidebar />
    <main className="flex-1 overflow-auto" id="main-content">
      <Outlet />
    </main>
  </div>
);

export default Layout;
