/** Document type to color mapping. */
export const DOC_TYPE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  CSP:                        { bg: 'bg-blue-50',    text: 'text-blue-700',   border: 'border-blue-200' },
  ICF:                        { bg: 'bg-green-50',   text: 'text-green-700',  border: 'border-green-200' },
  IB:                         { bg: 'bg-orange-50',  text: 'text-orange-700', border: 'border-orange-200' },
  CRF:                        { bg: 'bg-violet-50',  text: 'text-violet-700', border: 'border-violet-200' },
  CSR:                        { bg: 'bg-cyan-50',    text: 'text-cyan-700',   border: 'border-cyan-200' },
  eTMF:                       { bg: 'bg-slate-50',   text: 'text-slate-700',  border: 'border-slate-200' },
  'SmPC / DSUR / DSMB Charter': { bg: 'bg-pink-50',   text: 'text-pink-700',   border: 'border-pink-200' },
  Synopsis:                   { bg: 'bg-yellow-50',  text: 'text-yellow-700', border: 'border-yellow-200' },
  'Patient Questionnaire':    { bg: 'bg-indigo-50',  text: 'text-indigo-700', border: 'border-indigo-200' },
  'Info Sheet':               { bg: 'bg-teal-50',    text: 'text-teal-700',   border: 'border-teal-200' },
  'Medical Publications':     { bg: 'bg-rose-50',    text: 'text-rose-700',   border: 'border-rose-200' },
  NOISE:                      { bg: 'bg-gray-50',    text: 'text-gray-500',   border: 'border-gray-200' },
};

export function getDocColor(type: string) {
  return DOC_TYPE_COLORS[type] ?? { bg: 'bg-slate-50', text: 'text-slate-600', border: 'border-slate-200' };
}

/** Node colors for React Flow (hex). */
export const DOC_TYPE_HEX: Record<string, string> = {
  CSP: '#2563eb',
  ICF: '#16a34a',
  IB: '#ea580c',
  CRF: '#8b5cf6',
  CSR: '#0891b2',
  eTMF: '#475569',
  'SmPC / DSUR / DSMB Charter': '#c026d3',
  Synopsis: '#ca8a04',
  'Patient Questionnaire': '#4f46e5',
  'Info Sheet': '#0d9488',
  'Medical Publications': '#be185d',
  NOISE: '#9ca3af',
};

/** Trial node color (hex). */
export const TRIAL_HEX = '#dc2626';

export function getDocHex(type: string): string {
  return DOC_TYPE_HEX[type] ?? '#94a3b8';
}

export const EDGE_COLORS: Record<string, string> = {
  Supersedes: '#ef4444',
  DerivedFrom: '#3b82f6',
  References: '#9ca3af',
  Governs: '#a855f7',
  BelongsToTrial: '#d1d5db',
};
