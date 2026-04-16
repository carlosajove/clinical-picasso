import type { DocumentSummary } from '@/types';
import { getDocColor } from '@/lib/colors';
import { X } from 'lucide-react';

interface Props {
  doc: DocumentSummary;
  onClose: () => void;
}

export default function DocumentDetailSheet({ doc, onClose }: Props) {
  const color = getDocColor(doc.document_type);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/20" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-white shadow-xl overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 truncate">{doc.filename}</h2>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded-lg">
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${color.bg} ${color.text} border ${color.border}`}>
              {doc.document_type}
            </span>
            <span className="text-sm text-slate-500">
              {(doc.confidence * 100).toFixed(0)}% confidence
            </span>
          </div>

          {doc.summary && (
            <div>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">Summary</h3>
              <p className="text-sm text-slate-700 leading-relaxed">{doc.summary}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            {([
              ['Version', doc.version],
              ['Country', doc.country],
              ['Site', doc.site_id],
              ['Phase', doc.phase],
              ['Protocol', doc.sponsor_protocol_id],
              ['Sponsor', doc.sponsor_name],
              ['Intervention', doc.intervention],
              ['Indication', doc.indication],
              ['Therapeutic Area', doc.therapeutic_area],
            ] as [string, string | null][]).map(([label, value]) => (
              <div key={label}>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">{label}</p>
                <p className="text-sm text-slate-700 mt-0.5">{value ?? '—'}</p>
              </div>
            ))}
          </div>

          {doc.references_to.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">References</h3>
              <ul className="space-y-1">
                {doc.references_to.map((ref, i) => (
                  <li key={i} className="text-sm text-slate-600 bg-slate-50 px-3 py-1.5 rounded-lg">
                    {ref}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <p className="text-xs text-slate-400">ID: {doc.doc_id}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
