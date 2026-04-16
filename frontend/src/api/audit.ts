import { get } from './client';
import type { AuditReport } from '@/types';

export const fetchAuditReport = () => get<AuditReport>('/audit/report');
