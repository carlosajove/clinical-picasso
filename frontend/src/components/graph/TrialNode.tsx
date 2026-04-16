import { Handle, Position, type NodeProps } from '@xyflow/react';

export default function TrialNode({ data }: NodeProps) {
  const d = data as Record<string, string | undefined>;

  return (
    <div className="px-4 py-2 rounded-lg bg-primary text-white shadow-md border-2 border-primary-light min-w-[160px]">
      <Handle type="target" position={Position.Top} className="!bg-white !w-2 !h-2" />

      <div className="flex items-center gap-2">
        <span className="text-[10px] font-bold bg-white/20 px-1.5 py-0.5 rounded">TRIAL</span>
        {d.phase ? <span className="text-[10px] bg-white/20 px-1.5 py-0.5 rounded">Phase {d.phase}</span> : null}
      </div>

      <p className="text-xs font-semibold mt-1 truncate max-w-[150px]">
        {d.trial_key || d.protocol_id || d.title || 'Unknown Trial'}
      </p>

      <Handle type="source" position={Position.Bottom} className="!bg-white !w-2 !h-2" />
    </div>
  );
}
