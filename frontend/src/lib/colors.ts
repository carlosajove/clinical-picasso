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
  CSP: '#3b82f6',
  ICF: '#22c55e',
  IB: '#f97316',
  CRF: '#8b5cf6',
  CSR: '#06b6d4',
  eTMF: '#64748b',
  'SmPC / DSUR / DSMB Charter': '#ec4899',
  Synopsis: '#eab308',
  'Patient Questionnaire': '#6366f1',
  'Info Sheet': '#14b8a6',
  'Medical Publications': '#f43f5e',
  NOISE: '#9ca3af',
};

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
