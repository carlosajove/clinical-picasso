import type { CorpusStats } from '@/types';
import StatCard from './StatCard';
import { FileText, Layers, FileType, Globe, FlaskConical, Pill } from 'lucide-react';

interface Props {
  stats: CorpusStats;
}

export default function StatsCardGrid({ stats }: Props) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <StatCard
        label="Total Documents"
        value={stats.total_documents}
        icon={<FileText size={18} />}
      />
      <StatCard
        label="Document Classes"
        value={stats.document_classes}
        icon={<Layers size={18} />}
      />
      <StatCard
        label="File Formats"
        value={stats.file_formats}
        icon={<FileType size={18} />}
      />
      <StatCard
        label="Clinical Trials"
        value={stats.trial_count}
        icon={<Globe size={18} />}
      />
      <StatCard
        label="Therapeutic Areas"
        value={stats.therapeutic_areas}
        icon={<FlaskConical size={18} />}
      />
      <StatCard
        label="Investigational Drugs"
        value={stats.interventions.length}
        icon={<Pill size={18} />}
      />
    </div>
  );
}
