import { useQuery } from '@tanstack/react-query';
import { fetchAuditReport } from '@/api/audit';
import { AlertTriangle, CheckCircle } from 'lucide-react';

export default function TopBar() {
  const { data: audit } = useQuery({
    queryKey: ['audit'],
    queryFn: fetchAuditReport,
    staleTime: 60_000,
    retry: false,
  });

  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-4">
        {audit && (
          <div className="flex items-center gap-3 text-sm">
            {audit.errors > 0 ? (
              <span className="flex items-center gap-1 text-red-600">
                <AlertTriangle size={14} />
                {audit.errors} errors
              </span>
            ) : (
              <span className="flex items-center gap-1 text-green-600">
                <CheckCircle size={14} />
                No errors
              </span>
            )}
            {audit.warnings > 0 && (
              <span className="flex items-center gap-1 text-amber-600">
                <AlertTriangle size={14} />
                {audit.warnings} warnings
              </span>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
