import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchStats, fetchDocuments } from '@/api/corpus';
import StatsCardGrid from './StatsCardGrid';
import DocumentTable from './DocumentTable';
import DocumentDetailSheet from './DocumentDetailSheet';
import type { DocumentSummary } from '@/types';

export default function DashboardView() {
  const { data: stats, isLoading: statsLoading } = useQuery({ queryKey: ['stats'], queryFn: fetchStats });
  const { data: documents, isLoading: docsLoading } = useQuery({ queryKey: ['documents'], queryFn: fetchDocuments });
  const [selected, setSelected] = useState<DocumentSummary | null>(null);

  if (statsLoading || docsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-slate-400">Loading corpus...</div>
      </div>
    );
  }

  if (!stats || !documents) return null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-primary mb-1">Document Corpus</h2>
        <p className="text-sm text-slate-500">Overview of all clinical trial documents in the system</p>
      </div>

      <StatsCardGrid stats={stats} />

      <div>
        <h3 className="text-lg font-semibold text-slate-700 mb-3">All Documents</h3>
        <DocumentTable documents={documents} onSelect={setSelected} />
      </div>

      {selected && (
        <DocumentDetailSheet doc={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
