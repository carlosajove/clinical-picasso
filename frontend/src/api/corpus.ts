import { get } from './client';
import type { CorpusStats, DocumentSummary, DocumentDetail } from '@/types';

export const fetchStats = () => get<CorpusStats>('/corpus/stats');
export const fetchDocuments = () => get<DocumentSummary[]>('/corpus/documents');
export const fetchDocument = (id: string) => get<DocumentDetail>(`/corpus/documents/${id}`);
