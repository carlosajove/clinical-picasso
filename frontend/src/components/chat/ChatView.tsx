import { useState, useRef, useEffect } from 'react';
import { askQuestion } from '@/api/chat';
import { Send, Bot, User, ChevronDown, ChevronRight, Loader2, FileText } from 'lucide-react';
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
                  <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center flex-shrink-0 mt-1">
                    <Bot size={14} className="text-white" />
                  </div>
                )}

                {msg.role === 'user' ? (
                  <div className="max-w-[80%] bg-primary text-white rounded-xl px-4 py-3">
                    <p className="text-sm">{msg.content}</p>
                  </div>
                ) : (
                  <div className="max-w-[85%] space-y-3">
                    {/* Explanation text */}
                    <p className="text-sm text-slate-700 leading-relaxed">{msg.content}</p>

                    {msg.response && (
                      <>
                        {/* Results as readable cards/table */}
                        {msg.response.rows.length > 0 && (
                          <ResultsDisplay rows={msg.response.rows} />
                        )}

                        {/* Collapsible query */}
                        <QueryBlock query={msg.response.gq_query} />

                        {msg.response.error && (
                          <div className="flex items-center gap-2 text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                            <span className="font-medium">Error:</span> {msg.response.error}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}

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

/** Clean up column names: "doc.source_file" → "Source File" */
function formatColumnName(col: string): string {
  const name = col.includes('.') ? col.split('.').pop()! : col;
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Format cell values for readability */
function formatValue(val: unknown): string {
  if (val === null || val === undefined) return '—';
  if (Array.isArray(val)) return val.join(', ');
  if (typeof val === 'object') return JSON.stringify(val, null, 2);
  return String(val);
}

/**
 * If there are few columns (1-2) and results look like key-value,
 * render as a list of cards. Otherwise render as a clean table.
 */
function ResultsDisplay({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) return null;
  const cols = Object.keys(rows[0]);
  const isSingleResult = rows.length === 1;
  const hasLongValues = rows.some((row) =>
    cols.some((col) => String(row[col] ?? '').length > 100)
  );

  // Single result with long values → card layout
  if (isSingleResult && hasLongValues) {
    return <ResultCard row={rows[0]} cols={cols} />;
  }

  // Multiple results → clean table
  return <CleanTable rows={rows} cols={cols} />;
}

function ResultCard({ row, cols }: { row: Record<string, unknown>; cols: string[] }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
      <div className="divide-y divide-slate-100">
        {cols.map((col) => {
          const val = formatValue(row[col]);
          const isLong = val.length > 80;
          return (
            <div key={col} className={`px-4 py-2.5 ${isLong ? 'space-y-1' : 'flex items-baseline justify-between gap-4'}`}>
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wide flex-shrink-0">
                {formatColumnName(col)}
              </span>
              <p className={`text-sm text-slate-700 ${isLong ? '' : 'text-right'}`}>
                {val}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CleanTable({ rows, cols }: { rows: Record<string, unknown>[]; cols: string[] }) {
  const [showAll, setShowAll] = useState(false);
  const limit = 10;
  const displayed = showAll ? rows : rows.slice(0, limit);
  const hasMore = rows.length > limit;

  return (
    <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
      <div className="px-3 py-2 bg-slate-50 border-b border-slate-200 flex items-center gap-2">
        <FileText size={12} className="text-slate-400" />
        <span className="text-xs font-medium text-slate-500">
          {rows.length} result{rows.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200">
              {cols.map((col) => (
                <th key={col} className="px-3 py-2 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap">
                  {formatColumnName(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {displayed.map((row, i) => (
              <tr key={i} className="hover:bg-slate-50 transition-colors">
                {cols.map((col) => {
                  const val = formatValue(row[col]);
                  return (
                    <td key={col} className="px-3 py-2 text-slate-700" title={val}>
                      <span className="line-clamp-2">{val}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hasMore && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="w-full text-xs text-blue-600 hover:text-blue-700 py-2 bg-slate-50 border-t border-slate-200 font-medium transition-colors"
        >
          {showAll ? 'Show less' : `Show all ${rows.length} results`}
        </button>
      )}
    </div>
  );
}
