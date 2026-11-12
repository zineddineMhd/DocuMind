import { Eye, FileText, Loader2, RefreshCw, Search, Sparkles, Trash2, UploadCloud } from "lucide-react";
import { useMemo, useRef, useState, type DragEvent, type FormEvent } from "react";
import { AnswerBody } from "../components/Answer";
import SourceViewer, { type ViewTarget } from "../components/SourceViewer";
import { ACCEPT, DocIcon, Empty, Modal, PageHeader, StatusBadge } from "../components/ui";
import { useApp } from "../hooks/useApp";
import { api, formatBytes, formatDate } from "../services/api";
import type { Doc, DocStatus, SearchResult } from "../types";

const FILTERS: { key: "all" | DocStatus; label: string }[] = [
  { key: "all", label: "Tous" }, { key: "ready", label: "Prêts" },
  { key: "processing", label: "En cours" }, { key: "failed", label: "En échec" },
];

export default function Documents() {
  const { documents, workspace, stats, uploadFiles, uploading, refreshDocuments, refreshStats, refreshWorkspaces, notify, fail } = useApp();
  const [filter, setFilter] = useState<"all" | DocStatus>("all");
  const [text, setText] = useState("");
  const [drag, setDrag] = useState(false);
  const [viewer, setViewer] = useState<ViewTarget | null>(null);
  const [confirm, setConfirm] = useState<Doc | null>(null);
  const [summaryDoc, setSummaryDoc] = useState<Doc | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const shown = useMemo(() => documents.filter((d) =>
    (filter === "all" || d.status === filter || (filter === "processing" && d.status === "pending")) &&
    d.filename.toLowerCase().includes(text.toLowerCase())), [documents, filter, text]);

  const onDrop = (e: DragEvent) => {
    e.preventDefault(); setDrag(false);
    uploadFiles(Array.from(e.dataTransfer.files));
  };

  const remove = async (d: Doc) => {
    setBusy(d.id);
    try {
      await api.deleteDocument(d.id);
      notify(`« ${d.filename} » supprimé (fichier, passages et vecteurs purgés).`, "success");
      await refreshDocuments();
      refreshStats().catch(() => {}); refreshWorkspaces().catch(() => {});
    } catch (e) { fail(e); } finally { setBusy(null); setConfirm(null); }
  };

  const reindex = async (d: Doc) => {
    setBusy(d.id);
    try { await api.reindex(d.id); await refreshDocuments(); } catch (e) { fail(e); } finally { setBusy(null); }
  };

  const summarize = async (d: Doc, refresh = false) => {
    setSummaryDoc(d);
    if (d.summary && !refresh) return;
    setBusy(d.id);
    try {
      const out = await api.summary(d.id, refresh);
      setSummaryDoc({ ...d, summary: out.summary, keywords: out.keywords });
      refreshDocuments().catch(() => {});
    } catch (e) { fail(e); setSummaryDoc(null); } finally { setBusy(null); }
  };

  const search = async (e: FormEvent) => {
    e.preventDefault();
    if (!workspace || !query.trim()) return;
    setSearching(true);
    try { setResults((await api.search(workspace.id, query.trim())).results); } catch (err) { fail(err); } finally { setSearching(false); }
  };

  const hasReady = documents.some((d) => d.status === "ready");

  return (
    <div className="mx-auto max-w-6xl p-5 lg:p-8">
      <PageHeader title="Mes documents" subtitle={`Espace « ${workspace?.name ?? ""} » · PDF, DOCX, TXT ou MD jusqu'à ${stats?.config.max_upload_mb ?? 20} Mo par fichier`} />

      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
        onClick={() => input.current?.click()} role="button" tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-8 text-center transition ${
          drag ? "border-brand-500 bg-brand-50" : "border-[#d4cfee] bg-white hover:border-brand-400 hover:bg-brand-50/50"}`}>
        <input ref={input} type="file" accept={ACCEPT} multiple hidden
          onChange={(e) => { uploadFiles(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
        <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-100 text-brand-700">
          {uploading ? <Loader2 size={22} className="animate-spin" /> : <UploadCloud size={22} />}
        </span>
        <p className="font-semibold">{uploading ? "Envoi en cours…" : "Glissez-déposez vos fichiers ici"}</p>
        <p className="text-sm text-ink-500">ou cliquez pour parcourir · l'indexation démarre automatiquement</p>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <div className="flex gap-1 rounded-xl border border-[#e3e0f0] bg-white p-1">
          {FILTERS.map((f) => (
            <button key={f.key} onClick={() => setFilter(f.key)} aria-pressed={filter === f.key}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${filter === f.key ? "bg-brand-600 text-white" : "text-ink-500 hover:bg-brand-50"}`}>{f.label}</button>
          ))}
        </div>
        <div className="relative min-w-[200px] flex-1">
          <Search size={16} className="absolute left-3 top-3 text-ink-300" />
          <input className="input !pl-9" placeholder="Filtrer par nom de fichier…" value={text} onChange={(e) => setText(e.target.value)} aria-label="Filtrer les documents" />
        </div>
      </div>

      <div className="card mt-3 overflow-hidden">
        {shown.length === 0 ? (
          <Empty icon={<FileText size={22} />} title={documents.length ? "Aucun document ne correspond" : "Aucun document dans cet espace"}>
            {documents.length ? "Modifiez le filtre ou la recherche." : "Déposez un premier fichier ci-dessus pour l'indexer."}
          </Empty>
        ) : (
          <div className="scroll-thin overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-[#eeecf6] text-left text-xs uppercase tracking-wide text-ink-500">
                  <th className="px-4 py-3 font-semibold">Document</th><th className="px-3 py-3 font-semibold">Taille</th>
                  <th className="px-3 py-3 font-semibold">Pages</th><th className="px-3 py-3 font-semibold">Ajouté</th>
                  <th className="px-3 py-3 font-semibold">Statut</th><th className="px-4 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f0eef7]">
                {shown.map((d) => (
                  <tr key={d.id} className="hover:bg-[#fbfaff]">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <DocIcon filename={d.filename} />
                        <div className="min-w-0">
                          <p className="max-w-[320px] truncate font-medium">{d.filename}</p>
                          {d.status === "failed" && d.error
                            ? <p className="max-w-[320px] truncate text-xs text-red-600" title={d.error}>{d.error}</p>
                            : d.status === "ready" && <p className="text-xs text-ink-500">{d.chunk_count} passages indexés</p>}
                        </div>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-ink-700">{formatBytes(d.file_size)}</td>
                    <td className="px-3 py-3 text-ink-700">{d.page_count ?? "—"}</td>
                    <td className="whitespace-nowrap px-3 py-3 text-ink-700">{formatDate(d.created_at)}</td>
                    <td className="px-3 py-3"><StatusBadge doc={d} /></td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <button className="icon-btn" disabled={d.status !== "ready"} onClick={() => setViewer({ document_id: d.id, filename: d.filename })} aria-label={`Aperçu de ${d.filename}`} title="Aperçu"><Eye size={16} /></button>
                        <button className="icon-btn" disabled={d.status !== "ready" || busy === d.id} onClick={() => summarize(d)} aria-label={`Résumé de ${d.filename}`} title="Résumé automatique"><Sparkles size={16} /></button>
                        <button className="icon-btn" disabled={d.status === "processing" || d.status === "pending" || busy === d.id} onClick={() => reindex(d)} aria-label={`Réindexer ${d.filename}`} title="Réindexer"><RefreshCw size={16} /></button>
                        <button className="icon-btn hover:!bg-red-50 hover:!text-red-600" disabled={busy === d.id} onClick={() => setConfirm(d)} aria-label={`Supprimer ${d.filename}`} title="Supprimer"><Trash2 size={16} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <section className="card mt-5 p-5">
        <h2 className="flex items-center gap-2 font-semibold"><Search size={18} className="text-brand-600" />Recherche sémantique</h2>
        <p className="mt-1 text-sm text-ink-500">Retrouvez les passages les plus proches d'une idée, même formulée autrement que dans le texte.</p>
        <form onSubmit={search} className="mt-3 flex gap-2">
          <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ex. : comment la fiabilité est-elle garantie ?" disabled={!hasReady} aria-label="Requête de recherche" />
          <button className="btn-primary shrink-0" disabled={!hasReady || searching || !query.trim()}>
            {searching ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}Rechercher
          </button>
        </form>
        {results && (
          <ul className="mt-4 space-y-2">
            {results.length === 0 && <li className="text-sm text-ink-500">Aucun passage trouvé.</li>}
            {results.map((r, i) => (
              <li key={r.chunk_id}>
                <button onClick={() => setViewer({ document_id: r.document_id, filename: r.filename, page: r.page, chunk_id: r.chunk_id })}
                  className="w-full rounded-xl border border-[#eeecf6] p-3 text-left transition hover:border-brand-300 hover:bg-brand-50/50">
                  <span className="mb-1 flex items-center gap-2 text-xs text-ink-500">
                    <span className="cite !mx-0 !translate-y-0">{i + 1}</span>
                    <span className="truncate font-semibold text-ink-700">{r.filename}</span>
                    {r.page && <span>· p. {r.page}</span>}
                    {r.similarity !== null && <span className="ml-auto shrink-0">similarité {(r.similarity * 100).toFixed(0)} %</span>}
                  </span>
                  <span className="line-clamp-3 text-sm text-ink-700">{r.text}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {viewer && <SourceViewer target={viewer} onClose={() => setViewer(null)} />}
      {confirm && (
        <Modal title="Supprimer ce document ?" onClose={() => setConfirm(null)}>
          <p className="text-sm text-ink-700">« {confirm.filename} » sera définitivement supprimé, ainsi que ses passages indexés et ses vecteurs. Les conversations existantes conserveront leurs citations, signalées comme indisponibles.</p>
          <div className="mt-5 flex justify-end gap-2">
            <button className="btn-ghost" onClick={() => setConfirm(null)}>Annuler</button>
            <button className="btn bg-red-600 text-white hover:bg-red-700" disabled={busy === confirm.id} onClick={() => remove(confirm)}>
              {busy === confirm.id && <Loader2 size={16} className="animate-spin" />}Supprimer
            </button>
          </div>
        </Modal>
      )}
      {summaryDoc && (
        <Modal title={`Résumé — ${summaryDoc.filename}`} onClose={() => setSummaryDoc(null)}>
          {summaryDoc.summary ? (
            <>
              <AnswerBody text={summaryDoc.summary} sources={[]} onCite={() => {}} />
              {!!summaryDoc.keywords?.length && <div className="mt-3 flex flex-wrap gap-1.5">{summaryDoc.keywords.map((k) => <span key={k} className="chip">{k}</span>)}</div>}
              <button className="mt-4 text-sm font-semibold text-brand-700 hover:underline" disabled={busy === summaryDoc.id} onClick={() => summarize(summaryDoc, true)}>
                {busy === summaryDoc.id ? "Génération…" : "Régénérer le résumé"}
              </button>
            </>
          ) : <p className="flex items-center gap-2 text-sm text-ink-500"><Loader2 size={16} className="animate-spin" />Génération du résumé par Gemini…</p>}
        </Modal>
      )}
    </div>
  );
}
