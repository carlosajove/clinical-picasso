import { get } from './client';
import type { CascadeResult } from '@/types';

export const fetchGraphExport = () => get<Record<string, unknown>[]>('/graph/export');
export const fetchCascade = (docId: string) => get<CascadeResult>(`/graph/cascade/${docId}`);
