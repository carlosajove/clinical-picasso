import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { useQueryClient } from '@tanstack/react-query';
import { sseUpload } from '@/api/client';
import { getDocColor } from '@/lib/colors';
import type { IngestStep, IngestClassification, IngestResult } from '@/types';
import { Upload, FileText, CheckCircle, Loader2, AlertCircle, Zap, Network } from 'lucide-react';

const STEPS = [
  { key: 'preprocessing', label: 'Preprocessing' },
  { key: 'extraction', label: 'Extracting Metadata (LLM)' },
  { key: 'ingestion', label: 'Graph Ingestion' },
];

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

      {/* Processing stepper */}
      {fileName && (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <FileText size={16} className="text-slate-400" />
            <span className="text-sm font-medium text-slate-700">{fileName}</span>
          </div>

          <div className="space-y-3">
            {STEPS.map(({ key, label }) => {
              const step = steps[key];
              const status: string = step?.status ?? 'pending';

              return (
                <div key={key} className="flex items-center gap-3">
                  {status === 'running' && <Loader2 size={16} className="text-blue-500 animate-spin" />}
                  {status === 'done' && <CheckCircle size={16} className="text-green-500" />}
                  {status === 'error' && <AlertCircle size={16} className="text-red-500" />}
                  {status === 'pending' && <div className="w-4 h-4 rounded-full border-2 border-slate-200" />}
                  <span className={`text-sm ${status === 'running' ? 'text-blue-600 font-medium' : status === 'done' ? 'text-green-700' : status === 'error' ? 'text-red-600' : 'text-slate-400'}`}>
                    {label}
                  </span>
                  {step?.cached && <span className="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">cached</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Classification result */}
      {classification && (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Classification Result</h3>
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${getDocColor(classification.document_type).bg} ${getDocColor(classification.document_type).text} border ${getDocColor(classification.document_type).border}`}>
              {classification.document_type}
            </span>
            <div className="flex items-center gap-2">
              <div className="w-20 h-2 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${classification.confidence >= 0.8 ? 'bg-green-500' : classification.confidence >= 0.6 ? 'bg-amber-500' : 'bg-red-500'}`}
                  style={{ width: `${classification.confidence * 100}%` }}
                />
              </div>
              <span className="text-xs text-slate-500">{(classification.confidence * 100).toFixed(0)}%</span>
            </div>
            {classification.trial && (
              <span className="text-xs text-slate-500 bg-slate-50 px-2 py-1 rounded">{classification.trial}</span>
            )}
          </div>
        </div>
      )}

      {/* Ingest result */}
      {result && (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Ingestion Changes</h3>
          <div className="space-y-2">
            {result.changes.map((c, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                  c.action === 'created_node' ? 'bg-green-50 text-green-700' :
                  c.action === 'created_edge' ? 'bg-blue-50 text-blue-700' :
                  'bg-amber-50 text-amber-700'
                }`}>
                  {c.action}
                </span>
                <span className="text-slate-600">{c.target_type}</span>
              </div>
            ))}
          </div>

          {result.is_orphan && (
            <p className="text-xs text-amber-600 mt-3 bg-amber-50 p-2 rounded-lg">
              This document has no connections to other documents or trials.
            </p>
          )}

          <div className="flex gap-2 mt-4">
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
        </div>
      )}
    </div>
  );
}
