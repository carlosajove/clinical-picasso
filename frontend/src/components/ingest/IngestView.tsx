import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { useQueryClient } from '@tanstack/react-query';
import { sseUpload } from '@/api/client';
import type { IngestStep, IngestClassification, IngestResult } from '@/types';
import { Upload, FileText, Zap, Network } from 'lucide-react';
import PipelineAnimation from './PipelineAnimation';

export default function IngestView() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [steps, setSteps] = useState<Record<string, IngestStep>>({});
  const [classification, setClassification] = useState<IngestClassification | null>(null);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [, setDone] = useState(false);
  const [fileName, setFileName] = useState('');
  const [processing, setProcessing] = useState(false);

  const onDrop = useCallback((files: File[]) => {
    if (files.length === 0 || processing) return;
    const file = files[0];
    setFileName(file.name);
    setSteps({});
    setClassification(null);
    setResult(null);
    setDone(false);
    setProcessing(true);

    const source = sseUpload('/ingest/upload', file);

    source.addEventListener('step', (data: unknown) => {
      const step = data as IngestStep;
      setSteps((prev) => ({ ...prev, [step.step]: step }));
    });

    source.addEventListener('classification', (data: unknown) => {
      setClassification(data as IngestClassification);
    });

    source.addEventListener('result', (data: unknown) => {
      setResult(data as IngestResult);
    });

    source.addEventListener('done', () => {
      setDone(true);
      setProcessing(false);
      // Invalidate cached queries so dashboard/graph refresh
      queryClient.invalidateQueries({ queryKey: ['stats'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['graph'] });
    });
  }, [processing, queryClient]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled: processing,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/html': ['.html'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
      'text/csv': ['.csv'],
    },
    maxFiles: 1,
  });

  const hasSupersedes = result?.changes.some((c) => c.target_type === 'Supersedes');

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-primary flex items-center gap-2">
          <Upload size={24} />
          Upload Document
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          Drop a clinical document to classify, link, and ingest it into the graph
        </p>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`bg-white rounded-xl border-2 border-dashed p-12 text-center cursor-pointer transition-colors ${
          isDragActive ? 'border-blue-400 bg-blue-50' :
          processing ? 'border-slate-200 bg-slate-50 cursor-not-allowed' :
          'border-slate-300 hover:border-blue-300 hover:bg-blue-50/30'
        }`}
      >
        <input {...getInputProps()} />
        <FileText size={40} className="mx-auto text-slate-300 mb-3" />
        {isDragActive ? (
          <p className="text-blue-600 font-medium">Drop the file here</p>
        ) : processing ? (
          <p className="text-slate-400">Processing...</p>
        ) : (
          <>
            <p className="text-slate-600 font-medium">Drag & drop a document here</p>
            <p className="text-sm text-slate-400 mt-1">PDF, DOCX, HTML, TXT, MD, or CSV</p>
          </>
        )}
      </div>

      {/* Pipeline animation — replaces the old 3-step stepper + classification card */}
      {fileName && (
        <>
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-slate-400" />
            <span className="text-sm font-medium text-slate-700">{fileName}</span>
          </div>
          <PipelineAnimation
            steps={steps}
            classification={classification}
            result={result}
          />
        </>
      )}

      {/* Action buttons after pipeline completes */}
      {result && (
        <div className="flex gap-2">
          <button
            onClick={() => navigate(`/graph`)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-light transition-colors"
          >
            <Network size={14} />
            View in Graph
          </button>
          {hasSupersedes && (
            <button
              onClick={() => navigate(`/cascade/${result.doc_id}`)}
              className="flex items-center gap-2 px-4 py-2 bg-white text-primary border border-primary rounded-lg text-sm font-medium hover:bg-blue-50 transition-colors"
            >
              <Zap size={14} />
              Run Cascade Analysis
            </button>
          )}
        </div>
      )}
    </div>
  );
}
