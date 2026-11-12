import {
  BarChart3, Download, FileText, GitCompareArrows, GraduationCap, Layers, Loader2, MessageSquarePlus, PanelRight,
  Send, Sparkles, Square, Tags, User as UserIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AssistantMessage, AnswerBody } from "../components/Answer";
import SourceViewer, { type ViewTarget } from "../components/SourceViewer";
import { DocIcon, Empty, ImportButton, Modal, StatusBadge } from "../components/ui";
import { useApp } from "../hooks/useApp";
import { api, ApiError, formatBytes, formatDate, formatTime } from "../services/api";
import type { ChatMessage, ChatMode, Conversation, Doc } from "../types";

const SUGGESTIONS = [
  "Quels sont les points essentiels de ces documents ?",
  "Quelles sont les principales conclusions ?",
  "Quels chiffres clés sont mentionnés ?",
];

export default function Chat() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const { workspace, documents, refreshDocuments, refreshStats, notify, fail } = useApp();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [title, setTitle] = useState<string | null>(null);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [input, setInput] = useState("");
  const [explain, setExplain] = useState(false);
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [viewer, setViewer] = useState<ViewTarget | null>(null);
  const [tab, setTab] = useState<"docs" | "history">("docs");
  const [panelOpen, setPanelOpen] = useState(false);
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [summarizing, setSummarizing] = useState(false);
  const skipLoad = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);

  const ready = useMemo(() => documents.filter((d) => d.status === "ready"), [documents]);
  const selected = useMemo(() => ready.filter((d) => !excluded.has(d.id)), [ready, excluded]);
  const indexing = documents.some((d) => d.status === "pending" || d.status === "processing");

  const loadConvs = useCallback(() => {
    if (workspace) api.conversations(workspace.id).then(setConvs).catch(() => {});
  }, [workspace]);
  useEffect(loadConvs, [loadConvs]);

  // chargement d'une conversation existante
  useEffect(() => {
    if (!conversationId) { setMessages([]); setTitle(null); return; }
    if (skipLoad.current === conversationId) { skipLoad.current = null; return; }
    setLoading(true);
    api.conversation(conversationId)
      .then((c) => { setMessages(c.messages); setTitle(c.title); })
      .catch((e) => { fail(e); navigate("/chat", { replace: true }); })
      .finally(() => setLoading(false));
  }, [conversationId, fail, navigate]);

  // une conversation appartient à un espace : retour à une discussion vide si l'espace change
  const wsRef = useRef(workspace?.id);
  useEffect(() => {
    if (wsRef.current && workspace && wsRef.current !== workspace.id) { setExcluded(new Set()); navigate("/chat"); }
    wsRef.current = workspace?.id;
  }, [workspace, navigate]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: sending ? "auto" : "smooth", block: "end" }); }, [messages, sending]);

  const patchLast = (fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((ms) => ms.map((m, i) => (i === ms.length - 1 ? fn(m) : m)));

  const send = async (question: string, mode: ChatMode) => {
    question = question.trim();
    if (!question || sending || !workspace) return;
    if (!selected.length) { notify("Sélectionnez au moins un document prêt.", "error"); return; }
    const now = new Date().toISOString();
    setMessages((ms) => [
      ...ms,
      { id: `tmp-u-${now}`, role: "user", content: question, status: null, feedback: null, sources: [], created_at: now },
      { id: `tmp-a-${now}`, role: "assistant", content: "", status: null, feedback: null, sources: [], created_at: now, streaming: true },
    ]);
    setInput("");
    setSending(true);
    abort.current = new AbortController();
    try {
      await api.chatStream(
        { workspace_id: workspace.id, conversation_id: conversationId ?? null, question, mode,
          document_ids: selected.length === ready.length ? [] : selected.map((d) => d.id) },
        (ev) => {
          if (ev.type === "meta") {
            if (!conversationId) {
              skipLoad.current = ev.conversation_id;
              setTitle(ev.title);
              navigate(`/chat/${ev.conversation_id}`, { replace: true });
            }
          } else if (ev.type === "token") {
            patchLast((m) => ({ ...m, content: m.content + ev.text }));
          } else if (ev.type === "final") {
            patchLast((m) => ({ ...m, id: ev.message_id, content: ev.answer, sources: ev.sources, status: ev.status,
              created_at: ev.created_at, streaming: false, metrics: ev.metrics }));
          } else if (ev.type === "error") {
            patchLast((m) => ({ ...m, content: ev.message, status: "error", streaming: false }));
          }
        },
        abort.current.signal,
      );
      patchLast((m) => (m.streaming ? { ...m, streaming: false, status: m.content ? "uncertain" : "error",
        content: m.content || "La réponse a été interrompue." } : m));
    } catch (e) {
      const aborted = (e as Error).name === "AbortError";
      const text = aborted ? "Génération interrompue." : e instanceof ApiError ? e.message : "Erreur inattendue.";
      patchLast((m) => ({ ...m, content: aborted && m.content ? m.content : text, status: aborted && m.content ? "uncertain" : "error", streaming: false }));
    } finally {
      setSending(false);
      abort.current = null;
      loadConvs();
      refreshStats().catch(() => {});
      textarea.current?.focus();
    }
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input, explain ? "explain" : "qa"); }
  };

  const toggle = (id: string) => setExcluded((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  const exportConv = async () => {
    if (!conversationId) return;
    try {
      const md = await api.exportConversation(conversationId);
      const url = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
      const a = document.createElement("a");
      a.href = url; a.download = `${(title ?? "conversation").slice(0, 50).replace(/[\\/:*?"<>|]/g, "_")}.md`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { fail(e); }
  };

  const summarize = async (doc: Doc, refresh = false) => {
    setSummarizing(true);
    try { await api.summary(doc.id, refresh); await refreshDocuments(); } catch (e) { fail(e); } finally { setSummarizing(false); }
  };

  const single = selected.length === 1 ? selected[0] : null;
  const keywords = Array.from(new Set(selected.flatMap((d) => d.keywords ?? []))).slice(0, 10);
  const canSend = !sending && selected.length > 0 && input.trim().length > 0;

  const panel = (
    <div className="flex flex-col gap-4">
      <div className="card overflow-hidden">
        <div className="grid grid-cols-2 border-b border-[#eeecf6] text-sm font-semibold" role="tablist">
          {(["docs", "history"] as const).map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
              className={`py-3 transition ${tab === t ? "border-b-2 border-brand-600 text-brand-700" : "text-ink-500 hover:text-ink-900"}`}>
              {t === "docs" ? "Documents" : "Historique"}
            </button>
          ))}
        </div>
        {tab === "docs" ? (
          <div className="p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-semibold">Sélectionnés ({selected.length}/{ready.length})</p>
              <ImportButton className="btn-ghost !px-2.5 !py-1.5 !text-xs" label="Ajouter" />
            </div>
            {documents.length === 0 && <p className="py-4 text-center text-sm text-ink-500">Aucun document dans cet espace.</p>}
            <ul className="scroll-thin max-h-[38vh] divide-y divide-[#f0eef7] overflow-auto">
              {documents.map((d) => (
                <li key={d.id} className="flex items-center gap-2.5 py-2.5">
                  <DocIcon filename={d.filename} size={34} />
                  <button className="min-w-0 flex-1 text-left" onClick={() => d.status === "ready" && setViewer({ document_id: d.id, filename: d.filename })}
                    disabled={d.status !== "ready"} title={d.status === "ready" ? "Ouvrir le document" : d.error ?? ""}>
                    <span className="block truncate text-sm font-medium">{d.filename}</span>
                    <span className="block text-xs text-ink-500">
                      {formatBytes(d.file_size)}{d.page_count ? ` · ${d.page_count} pages` : ""}
                    </span>
                  </button>
                  {d.status === "ready"
                    ? <input type="checkbox" className="h-4 w-4 accent-brand-600" checked={!excluded.has(d.id)} onChange={() => toggle(d.id)}
                        aria-label={`Inclure ${d.filename} dans la discussion`} />
                    : <StatusBadge doc={d} compact />}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="p-3">
            <button className="btn-ghost mb-2 w-full !py-2" onClick={() => { navigate("/chat"); setPanelOpen(false); }}>
              <MessageSquarePlus size={16} />Nouvelle conversation
            </button>
            {convs.length === 0 && <p className="py-4 text-center text-sm text-ink-500">Aucune conversation.</p>}
            <ul className="scroll-thin max-h-[52vh] overflow-auto">
              {convs.map((c) => (
                <li key={c.id}>
                  <button onClick={() => { navigate(`/chat/${c.id}`); setPanelOpen(false); }}
                    className={`w-full rounded-xl px-3 py-2 text-left transition hover:bg-brand-50 ${c.id === conversationId ? "bg-brand-50" : ""}`}>
                    <span className="block truncate text-sm font-medium">{c.title}</span>
                    <span className="block text-xs text-ink-500">{formatDate(c.updated_at)} · {c.message_count} messages</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {tab === "docs" && (
        <>
          <div className="card p-4">
            <p className="mb-2 flex items-center gap-2 text-sm font-semibold"><FileText size={16} className="text-brand-600" />Résumé automatique</p>
            {single ? (
              single.summary ? (
                <>
                  <div className="scroll-thin max-h-56 overflow-auto text-[13px]"><AnswerBody text={single.summary} sources={[]} onCite={() => {}} /></div>
                  <button className="mt-2 text-xs font-semibold text-brand-700 hover:underline" disabled={summarizing} onClick={() => summarize(single, true)}>
                    {summarizing ? "Génération…" : "Régénérer"}
                  </button>
                </>
              ) : (
                <button className="btn-ghost w-full !bg-brand-50 !text-brand-700" disabled={summarizing} onClick={() => summarize(single)}>
                  {summarizing ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}Générer un résumé
                </button>
              )
            ) : (
              <p className="text-sm text-ink-500">Sélectionnez un seul document pour afficher son résumé, ou utilisez « Résumer » pour une synthèse du corpus.</p>
            )}
          </div>
          {keywords.length > 0 && (
            <div className="card p-4">
              <p className="mb-2 flex items-center gap-2 text-sm font-semibold"><Tags size={16} className="text-brand-600" />Mots-clés principaux</p>
              <div className="flex flex-wrap gap-1.5">{keywords.map((k) => <span key={k} className="chip">{k}</span>)}</div>
            </div>
          )}
        </>
      )}
    </div>
  );

  return (
    <div className="flex h-full">
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center justify-between gap-2 px-5 pb-3 pt-5 lg:px-8">
          <div className="min-w-0">
            <h1 className="truncate text-xl font-bold tracking-tight lg:text-2xl">{title ?? "Discussion avec vos documents"}</h1>
            <p className="mt-0.5 truncate text-sm text-ink-500">
              {selected.length} document(s) sélectionné(s) dans « {workspace?.name} » · réponses fondées sur vos sources
            </p>
          </div>
          <div className="flex items-center gap-2">
            {conversationId && <button className="btn-ghost !py-2" onClick={exportConv}><Download size={16} /><span className="hidden sm:inline">Exporter</span></button>}
            <button className="btn-ghost !py-2" onClick={() => navigate("/chat")}><MessageSquarePlus size={16} /><span className="hidden sm:inline">Nouvelle conversation</span></button>
            <button className="btn-ghost !px-2.5 !py-2 xl:hidden" onClick={() => setPanelOpen(true)} aria-label="Documents et historique"><PanelRight size={16} /></button>
          </div>
        </div>

        <div className="scroll-thin min-h-0 flex-1 overflow-auto px-5 lg:px-8">
          <div className="mx-auto flex max-w-3xl flex-col gap-5 pb-4">
            {loading && <p className="flex items-center justify-center gap-2 py-10 text-sm text-ink-500"><Loader2 size={16} className="animate-spin" />Chargement…</p>}
            {!loading && messages.length === 0 && (
              <div className="card mt-4">
                {ready.length === 0 ? (
                  <Empty icon={indexing ? <Loader2 size={22} className="animate-spin" /> : <FileText size={22} />}
                    title={indexing ? "Indexation en cours…" : "Importez un document pour commencer"}>
                    {indexing ? "Vous pourrez poser vos questions dès que vos documents seront prêts."
                      : <div className="mt-3 flex justify-center"><ImportButton /></div>}
                  </Empty>
                ) : (
                  <Empty icon={<Layers size={22} />} title="Posez une question sur vos documents">
                    <p>Les réponses citent les passages exacts ; cliquez sur une citation pour ouvrir la source.</p>
                    <div className="mt-4 flex flex-col gap-2">
                      {SUGGESTIONS.map((s) => (
                        <button key={s} className="rounded-xl border border-[#e3e0f0] px-3 py-2 text-sm text-ink-700 transition hover:border-brand-300 hover:bg-brand-50"
                          onClick={() => send(s, "qa")}>{s}</button>
                      ))}
                    </div>
                  </Empty>
                )}
              </div>
            )}
            {messages.map((m) => m.role === "user" ? (
              <div key={m.id} className="flex items-start justify-end gap-3">
                <div className="max-w-[85%]">
                  <div className="whitespace-pre-wrap rounded-2xl rounded-tr-md bg-brand-100/70 px-4 py-2.5 text-[15px]">{m.content}</div>
                  <p className="mt-1 text-right text-xs text-ink-300">{formatTime(m.created_at)}</p>
                </div>
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-700"><UserIcon size={17} /></span>
              </div>
            ) : (
              <div key={m.id} className="flex items-start gap-3">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 text-white"><Sparkles size={17} /></span>
                <div className="card min-w-0 flex-1 px-4 py-3">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-sm font-semibold">DocuMind</span>
                    <span className="text-xs text-ink-300">{formatTime(m.created_at)}</span>
                  </div>
                  {m.streaming && !m.content
                    ? <p className="flex items-center gap-2 py-1 text-sm text-ink-500"><Loader2 size={15} className="animate-spin" />Recherche des passages pertinents…</p>
                    : <AssistantMessage msg={m} onCite={(s) => setViewer(s)} />}
                </div>
              </div>
            ))}
            <div ref={bottom} />
          </div>
        </div>

        <div className="px-5 pb-5 pt-2 lg:px-8">
          <div className="mx-auto max-w-3xl">
            <div className="mb-2 flex flex-wrap gap-2">
              <button className="btn-ghost !rounded-full !py-1.5 !text-[13px]" disabled={sending || !selected.length}
                onClick={() => send("Résume les points clés des documents sélectionnés.", "summary")}><Sparkles size={14} />Résumer</button>
              <button className="btn-ghost !rounded-full !py-1.5 !text-[13px]" disabled={sending || !selected.length}
                onClick={() => send("Extrais les chiffres clés et les données importantes des documents sélectionnés.", "summary")}><BarChart3 size={14} />Chiffres clés</button>
              <button className="btn-ghost !rounded-full !py-1.5 !text-[13px]" disabled={sending || selected.length < 2}
                title={selected.length < 2 ? "Sélectionnez au moins deux documents" : ""}
                onClick={() => send("Compare les documents sélectionnés : points communs, différences et conclusions.", "compare")}><GitCompareArrows size={14} />Comparer</button>
              <button className={`btn !rounded-full border !py-1.5 !text-[13px] ${explain ? "border-brand-600 bg-brand-600 text-white" : "border-[#e3e0f0] bg-white text-ink-700 hover:bg-brand-50"}`}
                aria-pressed={explain} onClick={() => setExplain((x) => !x)} title="Réponses pédagogiques, étape par étape"><GraduationCap size={14} />Expliquer</button>
            </div>
            <div className="card flex items-end gap-2 p-2.5 focus-within:border-brand-300 focus-within:ring-2 focus-within:ring-brand-100">
              <textarea ref={textarea} rows={1} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey}
                placeholder={selected.length ? "Posez une question sur vos documents…" : indexing ? "Indexation en cours…" : "Importez ou sélectionnez un document pour poser une question"}
                disabled={!selected.length} aria-label="Votre question"
                className="max-h-40 min-h-[44px] flex-1 resize-none bg-transparent px-2.5 py-2.5 text-[15px] placeholder:text-ink-300 focus:outline-none disabled:cursor-not-allowed"
                style={{ height: Math.min(160, 44 + (input.split("\n").length - 1) * 22) }} />
              {sending ? (
                <button className="btn-ghost !h-11 !w-11 !p-0" onClick={() => abort.current?.abort()} aria-label="Arrêter la génération"><Square size={16} /></button>
              ) : (
                <button className="btn-primary !h-11 !w-11 !p-0" disabled={!canSend} onClick={() => send(input, explain ? "explain" : "qa")} aria-label="Envoyer"><Send size={17} /></button>
              )}
            </div>
            <p className="mt-1.5 text-center text-[11px] text-ink-300">DocuMind peut se tromper : vérifiez les passages cités. Entrée pour envoyer, Maj+Entrée pour un saut de ligne.</p>
          </div>
        </div>
      </div>

      <aside className="scroll-thin hidden w-[340px] shrink-0 overflow-auto border-l border-[#e9e7f3] bg-[#faf9fe] p-4 xl:block">{panel}</aside>
      {panelOpen && <Modal title="Documents et historique" onClose={() => setPanelOpen(false)}>{panel}</Modal>}
      {viewer && <SourceViewer target={viewer} onClose={() => setViewer(null)} />}
    </div>
  );
}
