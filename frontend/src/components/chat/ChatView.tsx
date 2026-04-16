import { useState, useRef, useEffect } from 'react';
import { askQuestion } from '@/api/chat';
import { Send, Bot, User, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import type { ChatResponse } from '@/types';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  response?: ChatResponse;
}

const SUGGESTIONS = [
  'Which documents reference the protocol?',
  'Show all ICFs in the system',
  'Find orphan documents with no connections',
  'Which documents are superseded?',
  'What trials are in the graph?',
  'Show documents with low classification confidence',
];

export default function ChatView() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const send = async (question: string) => {
    if (!question.trim() || loading) return;

    const userMsg: Message = { role: 'user', content: question };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await askQuestion(question);
      const assistantMsg: Message = {
        role: 'assistant',
        content: res.explanation,
        response: res,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-140px)]">
      <div className="mb-4">
        <h2 className="text-2xl font-bold text-primary">Graph Chat</h2>
        <p className="text-sm text-slate-500">Ask natural language questions about the document graph</p>
      </div>

      <div className="flex-1 flex gap-4 min-h-0">
        {/* Chat thread */}
        <div className="flex-1 flex flex-col bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                <Bot size={40} className="text-slate-300 mb-3" />
                <p className="text-slate-500 text-sm mb-4">Ask a question about the document graph</p>
                <div className="flex flex-wrap gap-2 max-w-md justify-center">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="text-xs px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-full text-slate-600 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-200 transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                {msg.role === 'assistant' && (
                  <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                    <Bot size={14} className="text-white" />
                  </div>
                )}
                <div className={`max-w-[80%] ${msg.role === 'user' ? 'bg-primary text-white' : 'bg-slate-50'} rounded-xl px-4 py-3`}>
                  <p className="text-sm">{msg.content}</p>

                  {msg.response && (
                    <div className="mt-3 space-y-2">
                      <QueryBlock query={msg.response.gq_query} />
                      {msg.response.rows.length > 0 && <ResultsTable rows={msg.response.rows} />}
                      {msg.response.error && (
                        <p className="text-xs text-red-500 mt-1">{msg.response.error}</p>
                      )}
                    </div>
                  )}
                </div>
                {msg.role === 'user' && (
                  <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0">
                    <User size={14} className="text-slate-600" />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex items-center gap-2 text-slate-400 text-sm">
                <Loader2 size={14} className="animate-spin" />
                Generating query...
              </div>
            )}
          </div>

          {/* Input */}
          <div className="border-t border-slate-200 p-3">
            <form
              onSubmit={(e) => { e.preventDefault(); send(input); }}
              className="flex gap-2"
            >
              <input
                type="text"
                placeholder="Ask about the document graph..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={loading}
                className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-200 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!input.trim() || loading}
                className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-light disabled:opacity-50 transition-colors"
              >
                <Send size={14} />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

function QueryBlock({ query }: { query: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1 px-3 py-1.5 text-[10px] font-medium text-slate-500 bg-slate-100 hover:bg-slate-200 transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        Generated .gq query
      </button>
      {open && (
        <pre className="px-3 py-2 text-[11px] text-slate-700 bg-slate-50 overflow-x-auto font-mono">
          {query}
        </pre>
      )}
    </div>
  );
}

function ResultsTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) return null;
  const cols = Object.keys(rows[0]);

  return (
    <div className="border border-slate-200 rounded-lg overflow-x-auto">
      <table className="w-full text-[11px]">
        <thead>
          <tr className="bg-slate-100">
            {cols.map((col) => (
              <th key={col} className="px-2 py-1 text-left font-medium text-slate-500">{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 20).map((row, i) => (
            <tr key={i} className="border-t border-slate-100">
              {cols.map((col) => (
                <td key={col} className="px-2 py-1 text-slate-600 truncate max-w-[150px]">
                  {String(row[col] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 20 && (
        <p className="text-[10px] text-slate-400 px-2 py-1 bg-slate-50">Showing 20 of {rows.length} results</p>
      )}
    </div>
  );
}
