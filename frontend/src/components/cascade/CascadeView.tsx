import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchCascade } from '@/api/graph';
import { fetchDocuments } from '@/api/corpus';
import { getDocColor } from '@/lib/colors';
import { Zap, ArrowDownRight, Link2, Shield, Search } from 'lucide-react';

export default function CascadeView() {
  const { docId } = useParams<{ docId: string }>();
  const [selectedDocId, setSelectedDocId] = useState(docId || '');
  const [inputValue, setInputValue] = useState(docId || '');

  const { data: documents } = useQuery({ queryKey: ['documents'], queryFn: fetchDocuments });

  const { data: cascade, isLoading, error } = useQuery({
    queryKey: ['cascade', selectedDocId],
    queryFn: () => fetchCascade(selectedDocId),
    enabled: !!selectedDocId,
  });

  const sourceDoc = documents?.find((d) => d.doc_id === selectedDocId);

  const runCascade = () => {
    if (inputValue) setSelectedDocId(inputValue);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-primary flex items-center gap-2">
          <Zap size={24} />
          Cascade Impact Analysis
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          Trace which documents are affected by a change to a specific document
        </p>
      </div>

      {/* Document picker */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <label className="text-sm font-medium text-slate-700 mb-2 block">Select a document to analyze</label>
        <div className="flex gap-2">
          {documents ? (
            <select
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-200"
            >
              <option value="">Choose a document...</option>
              {documents.map((d) => (
                <option key={d.doc_id} value={d.doc_id}>
                  {d.filename} ({d.document_type}{d.version ? ` v${d.version}` : ''})
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              placeholder="Enter document ID..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
          )}
          <button
            onClick={runCascade}
            disabled={!inputValue}
            className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-light disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            <Search size={14} />
            Analyze
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center h-32">
          <div className="animate-pulse text-slate-400">Running cascade analysis...</div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          Failed to run cascade analysis. Make sure the graph is initialized.
        </div>
      )}

      {cascade && (
        <>
          {/* Source document card */}
          {sourceDoc && (
            <div className="bg-white rounded-xl border-2 border-primary p-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold text-primary bg-blue-50 px-2 py-0.5 rounded">SOURCE</span>
                <span className={`text-xs px-2 py-0.5 rounded ${getDocColor(sourceDoc.document_type).bg} ${getDocColor(sourceDoc.document_type).text}`}>
                  {sourceDoc.document_type}
                </span>
                {sourceDoc.version && <span className="text-xs text-slate-400">v{sourceDoc.version}</span>}
              </div>
              <p className="font-medium text-slate-900">{sourceDoc.filename}</p>
              {sourceDoc.summary && <p className="text-sm text-slate-500 mt-1 line-clamp-2">{sourceDoc.summary}</p>}
            </div>
          )}

          {/* Three columns */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <CascadeColumn
              title="Derived Downstream"
              icon={<ArrowDownRight size={16} />}
              items={cascade.derived}
              color="blue"
            />
            <CascadeColumn
              title="Referencing Documents"
              icon={<Link2 size={16} />}
              items={cascade.references}
              color="gray"
            />
            <CascadeColumn
              title="Governed Documents"
              icon={<Shield size={16} />}
              items={cascade.governed}
              color="purple"
            />
          </div>

          {/* Summary */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
            <p className="text-lg font-bold text-primary">
              {cascade.total_affected} document{cascade.total_affected !== 1 ? 's' : ''} affected
            </p>
            <p className="text-sm text-slate-500 mt-1">
              {cascade.derived.length} derived, {cascade.references.length} referencing, {cascade.governed.length} governed
            </p>
          </div>
        </>
      )}
    </div>
  );
}

function CascadeColumn({
  title,
  icon,
  items,
  color,
}: {
  title: string;
  icon: React.ReactNode;
  items: Record<string, unknown>[];
  color: 'blue' | 'gray' | 'purple';
}) {
  const borderColor = { blue: 'border-blue-200', gray: 'border-slate-200', purple: 'border-purple-200' }[color];
  const headerBg = { blue: 'bg-blue-50', gray: 'bg-slate-50', purple: 'bg-purple-50' }[color];
  const headerText = { blue: 'text-blue-700', gray: 'text-slate-700', purple: 'text-purple-700' }[color];

  return (
    <div className={`bg-white rounded-xl border ${borderColor} overflow-hidden`}>
      <div className={`${headerBg} px-4 py-3 flex items-center gap-2`}>
        <span className={headerText}>{icon}</span>
        <h3 className={`text-sm font-semibold ${headerText}`}>{title}</h3>
        <span className={`ml-auto text-xs font-medium ${headerText} bg-white/60 px-2 py-0.5 rounded-full`}>
          {items.length}
        </span>
      </div>
      <div className="p-3 space-y-2 max-h-[400px] overflow-y-auto">
        {items.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-4">No affected documents</p>
        ) : (
          items.map((item, i) => {
            const docType = (item['affected.document_type'] ?? item['$affected.document_type'] ?? '') as string;
            const docColor = getDocColor(docType);
            return (
              <div key={i} className="border border-slate-100 rounded-lg p-3 hover:bg-slate-50 transition-colors">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${docColor.bg} ${docColor.text}`}>
                    {docType}
                  </span>
                </div>
                <p className="text-xs text-slate-700 font-medium truncate">
                  {(item['affected.source_file'] ?? item['$affected.source_file'] ?? item['affected.doc_id'] ?? '') as string}
                </p>
                <div className="flex gap-2 mt-1">
                  {(item['affected.country'] || item['$affected.country']) ? (
                    <span className="text-[10px] text-slate-400">
                      {String(item['affected.country'] ?? item['$affected.country'])}
                    </span>
                  ) : null}
                  {(item['affected.site_id'] || item['$affected.site_id']) ? (
                    <span className="text-[10px] text-slate-400">
                      {String(item['affected.site_id'] ?? item['$affected.site_id'])}
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
