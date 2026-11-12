import { Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import type { Chunk } from "../types";
import { DocIcon, Modal } from "./ui";

export interface ViewTarget {
  document_id: string | null; filename: string; page?: number | null; chunk_id?: string; excerpt?: string;
  available?: boolean;
}

/** Lecteur de sources : PDF ouvert à la page citée + passage indexé surligné. */
export default function SourceViewer({ target, onClose }: { target: ViewTarget; onClose: () => void }) {
  const isPdf = target.filename.toLowerCase().endsWith(".pdf");
  const available = target.available !== false && !!target.document_id;
  const [url, setUrl] = useState<string | null>(null);
  const [chunks, setChunks] = useState<Chunk[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mark = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!available) return;
    let revoke: string | null = null;
    let alive = true;
    const id = target.document_id!;
    if (isPdf) {
      api.fileBlob(id).then((b) => {
        if (!alive) return;
        revoke = URL.createObjectURL(b);
        setUrl(revoke);
      }).catch((e) => alive && setError(e.message));
    }
    api.chunks(id, target.chunk_id).then((c) => alive && setChunks(c)).catch((e) => alive && setError(e.message));
    return () => { alive = false; if (revoke) URL.revokeObjectURL(revoke); };
  }, [available, isPdf, target.document_id, target.chunk_id]);

  useEffect(() => { mark.current?.scrollIntoView({ block: "center" }); }, [chunks]);

  const passages = (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
        {target.chunk_id ? "Passage cité et contexte" : "Passages indexés"}
      </p>
      {!available && target.excerpt && (
        <>
          <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-3 text-sm text-ink-500">
            Ce document a été supprimé : la source n'est plus consultable. Extrait conservé dans l'historique :
          </p>
          <blockquote className="rounded-xl bg-brand-50 p-3 text-sm leading-relaxed">{target.excerpt}</blockquote>
        </>
      )}
      {available && !chunks && !error && <p className="flex items-center gap-2 text-sm text-ink-500"><Loader2 size={14} className="animate-spin" />Chargement…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {chunks?.map((c) => {
        const cited = c.id === target.chunk_id;
        return (
          <div key={c.id} ref={cited ? mark : undefined}
            className={`rounded-xl border p-3 text-sm leading-relaxed ${cited ? "border-brand-300 bg-brand-50 ring-1 ring-brand-200" : "border-[#eeecf6] bg-white text-ink-700"}`}>
            <p className="mb-1 text-[11px] font-semibold text-ink-500">
              {c.page ? `Page ${c.page}` : c.section ?? `Passage ${c.ordinal + 1}`}{cited && " · passage cité"}
            </p>
            <p className="whitespace-pre-wrap">{c.text}</p>
          </div>
        );
      })}
    </div>
  );

  return (
    <Modal wide={isPdf && available} onClose={onClose}
      title={<span className="flex items-center gap-2"><DocIcon filename={target.filename} size={26} />
        <span className="truncate">{target.filename}{target.page ? ` — page ${target.page}` : ""}</span></span>}>
      {isPdf && available ? (
        <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
          <div className="h-[70vh] overflow-hidden rounded-xl border border-[#e9e7f3] bg-slate-100">
            {url ? <iframe title={target.filename} src={`${url}#page=${target.page ?? 1}&view=FitH`} className="h-full w-full" />
              : <div className="flex h-full items-center justify-center text-sm text-ink-500"><Loader2 size={16} className="mr-2 animate-spin" />Chargement du PDF…</div>}
          </div>
          <div className="scroll-thin max-h-[70vh] overflow-auto pr-1">{passages}</div>
        </div>
      ) : <div className="scroll-thin max-h-[70vh] overflow-auto pr-1">{passages}</div>}
    </Modal>
  );
}
