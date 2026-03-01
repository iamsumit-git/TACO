// src/App.tsx — Root app with sidebar navigation
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Overview from './pages/Overview';
import Requests from './pages/Requests';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

function Sidebar() {
  return (
    <nav className="sidebar">
      <div className="sidebar-brand">🌮 TACO</div>
      <NavLink id="nav-overview" to="/" end className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        📊 Overview
      </NavLink>
      <NavLink id="nav-requests" to="/requests" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
        📋 Requests
      </NavLink>
    </nav>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="shell">
          <Sidebar />
          <main className="main">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/requests" element={<Requests />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
