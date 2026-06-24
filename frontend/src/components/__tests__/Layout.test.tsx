/**
 * Layout.test.tsx
 * ===============
 * Tests for the top-level Layout shell component.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Layout from '../Layout';
import { useAppStore } from '../../store/useAppStore';

vi.mock('../Sidebar',  () => ({ default: () => <div data-testid="sidebar" /> }));
vi.mock('../TopBar',   () => ({ default: () => <div data-testid="topbar" />  }));

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<div data-testid="outlet-content">outlet</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  useAppStore.setState({ sidebarCollapsed: false });
});

describe('Layout', () => {
  it('renders Sidebar and TopBar', () => {
    renderLayout();
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    expect(screen.getByTestId('topbar')).toBeInTheDocument();
  });

  it('renders the router Outlet', () => {
    renderLayout();
    expect(screen.getByTestId('outlet-content')).toBeInTheDocument();
  });

  it('sets marginLeft to 260px when sidebar is expanded', () => {
    useAppStore.setState({ sidebarCollapsed: false });
    renderLayout();
    const wrapper = document.querySelector('.transition-all') as HTMLElement;
    expect(wrapper?.style.marginLeft).toBe('260px');
  });

  it('sets marginLeft to 48px when sidebar is collapsed', () => {
    useAppStore.setState({ sidebarCollapsed: true });
    renderLayout();
    const wrapper = document.querySelector('.transition-all') as HTMLElement;
    expect(wrapper?.style.marginLeft).toBe('48px');
  });

  it('contains a <main> element for page content', () => {
    renderLayout();
    expect(document.querySelector('main')).toBeInTheDocument();
  });
});
