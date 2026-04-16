import { useState, useMemo } from 'react';
import type { DocumentSummary } from '@/types';
import { getDocColor } from '@/lib/colors';
import { Search, ChevronUp, ChevronDown } from 'lucide-react';

interface Props {
  documents: DocumentSummary[];
  onSelect: (doc: DocumentSummary) => void;
}

type SortKey = 'filename' | 'document_type' | 'confidence' | 'version' | 'country';

export default function DocumentTable({ documents, onSelect }: Props) {
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('confidence');
  const [sortAsc, setSortAsc] = useState(false);
  const [typeFilter, setTypeFilter] = useState<string>('');

  const types = useMemo(
    () => [...new Set(documents.map((d) => d.document_type))].sort(),
    [documents],
  );

  const filtered = useMemo(() => {
    let docs = documents;
    if (search) {
      const q = search.toLowerCase();
      docs = docs.filter(
        (d) =>
          d.filename.toLowerCase().includes(q) ||
          d.document_type.toLowerCase().includes(q) ||
          d.summary?.toLowerCase().includes(q) ||
          d.sponsor_protocol_id?.toLowerCase().includes(q),
      );
    }
    if (typeFilter) {
      docs = docs.filter((d) => d.document_type === typeFilter);
    }
    return [...docs].sort((a, b) => {
      const av = a[sortKey] ?? '';
      const bv = b[sortKey] ?? '';
      const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv));
      return sortAsc ? cmp : -cmp;
    });
  }, [documents, search, typeFilter, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(true); }
  };

  const SortIcon = ({ col }: { col: SortKey }) =>
    sortKey === col ? (sortAsc ? <ChevronUp size={14} /> : <ChevronDown size={14} />) : null;

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      {/* Toolbar */}
      <div className="p-4 border-b border-slate-100 flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search documents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-200"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-200"
        >
          <option value="">All types</option>
          {types.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <span className="text-sm text-slate-400">{filtered.length} documents</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-100">
              {([
                ['filename', 'Filename'],
                ['document_type', 'Type'],
                ['confidence', 'Confidence'],
                ['version', 'Version'],
                ['country', 'Country'],
              ] as [SortKey, string][]).map(([key, label]) => (
                <th
                  key={key}
                  className="px-4 py-3 font-medium cursor-pointer hover:text-slate-900 select-none"
                  onClick={() => toggleSort(key)}
                >
                  <span className="flex items-center gap-1">
                    {label} <SortIcon col={key} />
                  </span>
                </th>
              ))}
              <th className="px-4 py-3 font-medium">Trial</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((doc) => {
              const color = getDocColor(doc.document_type);
              return (
                <tr
                  key={doc.doc_id}
                  className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer transition-colors"
                  onClick={() => onSelect(doc)}
                >
                  <td className="px-4 py-3 font-medium text-slate-700 truncate max-w-[200px]">
                    {doc.filename}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${color.bg} ${color.text} border ${color.border}`}>
                      {doc.document_type}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            doc.confidence >= 0.8 ? 'bg-green-500' :
                            doc.confidence >= 0.6 ? 'bg-amber-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${doc.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-400">{(doc.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{doc.version ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-600">{doc.country ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-500 text-xs truncate max-w-[160px]">
                    {doc.sponsor_protocol_id ?? '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
