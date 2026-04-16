const BASE = '/api';

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path}: ${res.status}`);
  return res.json();
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path}: ${res.status}`);
  return res.json();
}

export function sseUpload(path: string, file: File): EventSource & { abort: () => void } {
  // We need to POST with FormData, then read SSE from the response.
  // Since EventSource only supports GET, we use fetch + ReadableStream.
  // Return a custom event-like interface.
  const controller = new AbortController();

  const formData = new FormData();
  formData.append('file', file);

  const listeners: Record<string, ((data: unknown) => void)[]> = {};

  const obj = {
    addEventListener(event: string, fn: (data: unknown) => void) {
      (listeners[event] ??= []).push(fn);
    },
    abort() {
      controller.abort();
    },
  };

  fetch(`${BASE}${path}`, {
    method: 'POST',
    body: formData,
    signal: controller.signal,
  }).then(async (res) => {
    const reader = res.body?.getReader();
    if (!reader) return;
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split('\n\n');
      buffer = parts.pop() ?? '';

      for (const part of parts) {
        const eventMatch = part.match(/^event: (.+)$/m);
        const dataMatch = part.match(/^data: (.+)$/m);
        if (eventMatch && dataMatch) {
          const event = eventMatch[1];
          const data = JSON.parse(dataMatch[1]);
          listeners[event]?.forEach((fn) => fn(data));
        }
      }
    }
  });

  return obj as EventSource & { abort: () => void };
}
