import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from '@/components/layout/Layout';
import DashboardView from '@/components/dashboard/DashboardView';
import GraphView from '@/components/graph/GraphView';
import ChatView from '@/components/chat/ChatView';
import IngestView from '@/components/ingest/IngestView';
import AuditView from '@/components/audit/AuditView';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardView />} />
            <Route path="/graph" element={<GraphView />} />
            <Route path="/chat" element={<ChatView />} />
            <Route path="/ingest" element={<IngestView />} />
            <Route path="/audit" element={<AuditView />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
