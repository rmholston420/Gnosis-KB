/**
 * ProtectedRoute
 * ==============
 * Reads auth state from useAppStore. Redirects to /login when unauthenticated.
 * Renders an <Outlet /> for all child routes when authenticated.
 */
import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAppStore } from '../store/appStore';

export function ProtectedRoute() {
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
