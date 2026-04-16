import { post } from './client';
import type { ChatResponse } from '@/types';

export const askQuestion = (question: string) =>
  post<ChatResponse>('/chat/ask', { question });
