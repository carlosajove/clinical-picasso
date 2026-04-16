import { Handle, Position, type NodeProps } from '@xyflow/react';
import { getDocColor } from '@/lib/colors';

export default function DocumentNode({ data }: NodeProps) {
  const d = data as Record<string, string | undefined>;
  const docType = d.document_type || 'Unknown';
  const color = getDocColor(docType);
  const status = d.status || 'active';
  const isSuperseded = status === 'superseded';

  return (
    <div
      className={`px-3 py-2 rounded-lg border-2 bg-white shadow-sm min-w-[180px] ${
        isSuperseded ? 'opacity-50 border-dashed border-slate-300' : `${color.border}`
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-300 !w-2 !h-2" />

      <div className="flex items-center gap-2 mb-1">
        <span className={`w-2 h-2 rounded-full ${isSuperseded ? 'bg-red-400' : 'bg-green-400'}`} />
        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${color.bg} ${color.text}`}>
          {docType}
        </span>
        {d.version ? <span className="text-[10px] text-slate-400">v{d.version}</span> : null}
      </div>

      <p className="text-xs text-slate-700 font-medium truncate max-w-[170px]">
        {d.source_file || d.doc_id || ''}
      </p>

      {d.country ? (
        <p className="text-[10px] text-slate-400 mt-0.5">{d.country}{d.site_id ? ` / ${d.site_id}` : ''}</p>
      ) : null}

      <Handle type="source" position={Position.Bottom} className="!bg-slate-300 !w-2 !h-2" />
    </div>
  );
}
