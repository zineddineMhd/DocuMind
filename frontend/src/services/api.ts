import type {
  ChatFinal, ChatMessage, ChatMode, Chunk, Conversation, Doc, SearchResult, Stats, User, Workspace,
} from "../types";

const TOKEN_KEY = "documind.token";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string) {
    super(message);
  }
}

export const auth = {
  get token() { return localStorage.getItem(TOKEN_KEY); },
  set(token: string) { localStorage.setItem(TOKEN_KEY, token); },
  clear() { localStorage.removeItem(TOKEN_KEY); },
};

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

function headers(extra?: HeadersInit): HeadersInit {
  return { ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}), ...extra };
}

async function toError(res: Response): Promise<ApiError> {
  let code = "error";
  let message = `Erreur ${res.status}`;
  let rid: string | undefined;
  try {
    const body = await res.json();
    if (body?.error) { code = body.error.code; message = body.error.message; rid = body.error.request_id; }
  } catch { /* corps non JSON */ }
  if (res.status === 401 && code !== "invalid_credentials") onUnauthorized();
  return new ApiError(res.status, code, message, rid);
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers: headers(body !== undefined ? { "Content-Type": "application/json" } : undefined),
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "network", "Serveur injoignable. Vérifiez que le backend est démarré.");
  }
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return (res.headers.get("content-type") ?? "").includes("json") ? res.json() : (res.text() as unknown as T);
}

interface TokenOut { access_token: string; user: User }
export interface UploadOut { documents: Doc[]; rejected: { filename: string; code: string; message: string }[] }

export interface ChatRequest {
  workspace_id: string; conversation_id: string | null; question: string; document_ids: string[]; mode: ChatMode;
}
export type StreamEvent =
  | { type: "meta"; conversation_id: string; title: string }
  | { type: "token"; text: string }
  | ({ type: "final" } & ChatFinal)
  | { type: "error"; status: number; code: string; message: string };

export const api = {
  register: (email: string, password: string, name: string) =>
    request<TokenOut>("POST", "/api/auth/register", { email, password, name }),
  login: (email: string, password: string) => request<TokenOut>("POST", "/api/auth/login", { email, password }),
  me: () => request<User>("GET", "/api/auth/me"),
  updateMe: (body: { name?: string; current_password?: string; new_password?: string }) =>
    request<User>("PATCH", "/api/auth/me", body),
  deleteMe: () => request<void>("DELETE", "/api/auth/me"),

  workspaces: () => request<Workspace[]>("GET", "/api/workspaces"),
  createWorkspace: (name: string) => request<Workspace>("POST", "/api/workspaces", { name }),
  renameWorkspace: (id: string, name: string) => request<Workspace>("PATCH", `/api/workspaces/${id}`, { name }),
  deleteWorkspace: (id: string) => request<void>("DELETE", `/api/workspaces/${id}`),

  documents: (workspaceId: string) => request<Doc[]>("GET", `/api/documents?workspace_id=${workspaceId}`),
  deleteDocument: (id: string) => request<void>("DELETE", `/api/documents/${id}`),
  reindex: (id: string) => request<Doc>("POST", `/api/documents/${id}/reindex`),
  summary: (id: string, refresh = false) =>
    request<{ summary: string; keywords: string[] }>("POST", `/api/documents/${id}/summary?refresh=${refresh}`),
  chunks: (id: string, around?: string) =>
    request<Chunk[]>("GET", `/api/documents/${id}/chunks${around ? `?around=${encodeURIComponent(around)}` : ""}`),
  async upload(workspaceId: string, files: File[]): Promise<UploadOut> {
    const form = new FormData();
    form.append("workspace_id", workspaceId);
    files.forEach((f) => form.append("files", f));
    const res = await fetch("/api/documents/upload", { method: "POST", headers: headers(), body: form });
    if (!res.ok) throw await toError(res);
    return res.json();
  },
  async fileBlob(id: string): Promise<Blob> {
    const res = await fetch(`/api/documents/${id}/file`, { headers: headers() });
    if (!res.ok) throw await toError(res);
    return res.blob();
  },

  conversations: (workspaceId: string) =>
    request<Conversation[]>("GET", `/api/conversations?workspace_id=${workspaceId}`),
  conversation: (id: string) => request<Conversation & { messages: ChatMessage[] }>("GET", `/api/conversations/${id}`),
  renameConversation: (id: string, title: string) =>
    request<Conversation>("PATCH", `/api/conversations/${id}`, { title }),
  deleteConversation: (id: string) => request<void>("DELETE", `/api/conversations/${id}`),
  exportConversation: (id: string) => request<string>("GET", `/api/conversations/${id}/export`),
  feedback: (messageId: string, value: -1 | 0 | 1) =>
    request<void>("POST", `/api/messages/${messageId}/feedback`, { value }),

  search: (workspaceId: string, query: string, documentIds?: string[]) =>
    request<{ results: SearchResult[]; search_ms: number }>("POST", "/api/search", {
      workspace_id: workspaceId, query, document_ids: documentIds?.length ? documentIds : null, top_k: 8,
    }),
  stats: () => request<Stats>("GET", "/api/stats"),

  /** Chat en streaming (Server-Sent Events sur une requête POST). */
  async chatStream(body: ChatRequest, onEvent: (ev: StreamEvent) => void, signal?: AbortSignal): Promise<void> {
    let res: Response;
    try {
      res = await fetch("/api/chat/stream", {
        method: "POST", headers: headers({ "Content-Type": "application/json" }), body: JSON.stringify(body), signal,
      });
    } catch (e) {
      if ((e as Error).name === "AbortError") throw e;
      throw new ApiError(0, "network", "Serveur injoignable. Vérifiez que le backend est démarré.");
    }
    if (!res.ok || !res.body) throw await toError(res);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) >= 0) {
        const line = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 2);
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)) as StreamEvent);
      }
    }
  },
};

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} Ko`;
  if (n < 1024 ** 3) return `${(n / 1024 / 1024).toFixed(1).replace(".", ",")} Mo`;
  return `${(n / 1024 ** 3).toFixed(2).replace(".", ",")} Go`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const day = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(today) - day(d)) / 86400000);
  if (diff === 0) return "aujourd'hui";
  if (diff === 1) return "hier";
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: d.getFullYear() === today.getFullYear() ? undefined : "numeric" });
}

export const formatTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
