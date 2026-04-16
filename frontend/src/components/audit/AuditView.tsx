import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchAuditReport } from '@/api/audit';
import {
  ShieldCheck,
  AlertTriangle,
  AlertCircle,
  Info,
  ChevronDown,
  ChevronRight,
  Download,
} from 'lucide-react';
import type { AuditIssue } from '@/types';

const CATEGORY_META: Record<string, { label: string; icon: React.ReactNode }> = {
  stale_parent: { label: 'Stale Parents', icon: <AlertCircle size={14} /> },
  stale_reference: { label: 'Stale References', icon: <AlertTriangle size={14} /> },
  stale_governance: { label: 'Stale Governance', icon: <AlertTriangle size={14} /> },
  orphan: { label: 'Orphan Documents', icon: <AlertTriangle size={14} /> },
  low_confidence: { label: 'Low Confidence', icon: <AlertTriangle size={14} /> },
  missing_doc_type: { label: 'Missing Document Types', icon: <Info size={14} /> },
  version_gap: { label: 'Version Gaps', icon: <Info size={14} /> },
  metadata_conflict: { label: 'Metadata Conflicts', icon: <AlertTriangle size={14} /> },
};

const SEVERITY_STYLE = {
  error: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', badge: 'bg-red-100 text-red-700' },
  warning: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', badge: 'bg-amber-100 text-amber-700' },
  info: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', badge: 'bg-blue-100 text-blue-700' },
};

export default function AuditView() {
  const { data: report, isLoading, error } = useQuery({ queryKey: ['audit-full'], queryFn: fetchAuditReport });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-slate-400">Running audit checks...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
        Failed to run audit. Make sure the graph is initialized.
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-primary flex items-center gap-2">
            <ShieldCheck size={24} />
            Audit Report
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Graph-wide inconsistency analysis across {report.total_issues} issues
          </p>
        </div>
        <a
          href="/api/audit/report/export"
          className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
        >
          <Download size={14} />
          Export JSON
        </a>
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-red-700">{report.errors}</p>
          <p className="text-sm text-red-600">Errors</p>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-amber-700">{report.warnings}</p>
          <p className="text-sm text-amber-600">Warnings</p>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-blue-700">
            {report.total_issues - report.errors - report.warnings}
          </p>
          <p className="text-sm text-blue-600">Info</p>
        </div>
      </div>

      {/* Category accordions */}
      <div className="space-y-3">
        {Object.entries(report.by_category).map(([category, issues]) => (
          <CategorySection key={category} category={category} issues={issues} />
        ))}
      </div>

      {report.total_issues === 0 && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-8 text-center">
          <ShieldCheck size={40} className="mx-auto text-green-500 mb-3" />
          <p className="text-green-700 font-semibold">All checks passed</p>
          <p className="text-sm text-green-600 mt-1">No inconsistencies found in the document graph</p>
        </div>
      )}
    </div>
  );
}

function CategorySection({ category, issues }: { category: string; issues: AuditIssue[] }) {
  const [open, setOpen] = useState(true);
  const meta = CATEGORY_META[category] ?? { label: category, icon: <Info size={14} /> };
  const primarySeverity = issues[0]?.severity ?? 'info';
  const style = SEVERITY_STYLE[primarySeverity];

  return (
    <div className={`bg-white rounded-xl border ${style.border} overflow-hidden`}>
      <button
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center gap-3 px-4 py-3 text-left ${style.bg} hover:opacity-90 transition-opacity`}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className={style.text}>{meta.icon}</span>
        <span className={`text-sm font-semibold ${style.text}`}>{meta.label}</span>
        <span className={`ml-auto text-xs font-medium px-2 py-0.5 rounded-full ${style.badge}`}>
          {issues.length}
        </span>
      </button>

      {open && (
        <div className="divide-y divide-slate-100">
          {issues.map((issue, i) => (
            <div key={i} className="px-4 py-3 hover:bg-slate-50 transition-colors">
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${SEVERITY_STYLE[issue.severity].badge}`}>
                  {issue.severity}
                </span>
                {issue.doc_id && (
                  <span className="text-[10px] text-slate-400 font-mono">{issue.doc_id}</span>
                )}
              </div>
              <p className="text-sm text-slate-700">{issue.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
