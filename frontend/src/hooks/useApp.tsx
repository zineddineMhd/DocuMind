import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, auth, setUnauthorizedHandler } from "../services/api";
import type { Doc, Stats, User, Workspace } from "../types";

interface Toast { id: number; kind: "info" | "error" | "success"; text: string }

interface AppState {
  user: User | null;
  booting: boolean;
  workspaces: Workspace[];
  workspace: Workspace | null;
  documents: Doc[];
  stats: Stats | null;
  toasts: Toast[];
  signIn(token: string, user: User): void;
  signOut(): void;
  setUser(u: User): void;
  selectWorkspace(id: string): void;
  refreshWorkspaces(): Promise<void>;
  refreshDocuments(): Promise<void>;
  refreshStats(): Promise<void>;
  uploadFiles(files: File[]): Promise<void>;
  uploading: boolean;
  notify(text: string, kind?: Toast["kind"]): void;
  fail(e: unknown): void;
}

const Ctx = createContext<AppState | null>(null);
const WS_KEY = "documind.workspace";

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState<string | null>(localStorage.getItem(WS_KEY));
  const [documents, setDocuments] = useState<Doc[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [uploading, setUploading] = useState(false);
  const toastId = useRef(0);

  const notify = useCallback((text: string, kind: Toast["kind"] = "info") => {
    const id = ++toastId.current;
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 7000 : 4000);
  }, []);
  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) return;
    notify(e instanceof Error ? e.message : "Erreur inattendue.", "error");
  }, [notify]);

  const signOut = useCallback(() => {
    auth.clear();
    setUser(null); setWorkspaces([]); setDocuments([]); setStats(null);
  }, []);
  useEffect(() => setUnauthorizedHandler(signOut), [signOut]);

  const workspace = useMemo(
    () => workspaces.find((w) => w.id === workspaceId) ?? workspaces[0] ?? null, [workspaces, workspaceId]);

  const refreshWorkspaces = useCallback(async () => { setWorkspaces(await api.workspaces()); }, []);
  const refreshStats = useCallback(async () => { setStats(await api.stats()); }, []);
  const wsId = workspace?.id;
  const refreshDocuments = useCallback(async () => {
    if (wsId) setDocuments(await api.documents(wsId));
  }, [wsId]);

  // démarrage : session existante ?
  useEffect(() => {
    if (!auth.token) { setBooting(false); return; }
    api.me().then(setUser).catch(() => auth.clear()).finally(() => setBooting(false));
  }, []);

  useEffect(() => {
    if (!user) return;
    refreshWorkspaces().catch(fail);
    refreshStats().catch(fail);
  }, [user, refreshWorkspaces, refreshStats, fail]);

  useEffect(() => {
    setDocuments([]);
    if (user && wsId) refreshDocuments().catch(fail);
  }, [user, wsId, refreshDocuments, fail]);

  // suivi de l'indexation : on interroge tant qu'un document est en attente / en cours
  const busy = documents.some((d) => d.status === "pending" || d.status === "processing");
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => { refreshDocuments().catch(() => {}); }, 1500);
    return () => { clearInterval(t); refreshStats().catch(() => {}); };
  }, [busy, refreshDocuments, refreshStats]);

  const uploadFiles = useCallback(async (files: File[]) => {
    if (!wsId || !files.length) return;
    setUploading(true);
    try {
      const out = await api.upload(wsId, files);
      out.rejected.forEach((r) => notify(r.message, "error"));
      if (out.documents.length)
        notify(`${out.documents.length} document(s) importé(s) — indexation en cours…`, "success");
      await refreshDocuments();
      refreshStats().catch(() => {});
      refreshWorkspaces().catch(() => {});
    } catch (e) { fail(e); } finally { setUploading(false); }
  }, [wsId, notify, fail, refreshDocuments, refreshStats, refreshWorkspaces]);

  const value: AppState = {
    user, booting, workspaces, workspace, documents, stats, toasts, uploading,
    signIn: (token, u) => { auth.set(token); setUser(u); },
    signOut, setUser,
    selectWorkspace: (id) => { localStorage.setItem(WS_KEY, id); setWorkspaceId(id); },
    refreshWorkspaces, refreshDocuments, refreshStats, uploadFiles, notify, fail,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp hors AppProvider");
  return ctx;
}
