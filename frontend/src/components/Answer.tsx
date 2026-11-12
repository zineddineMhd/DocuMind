import { AlertTriangle, Check, Copy, SearchX, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../services/api";
import type { ChatMessage, Source } from "../types";
import { DocIcon } from "./ui";

/** Transforme [S1] en liens internes que le rendu Markdown convertit en pastilles cliquables. */
function withCitations(text: string): string {
  // Gemini renvoie parfois du HTML (<code>, <br>) au lieu de Markdown : on le convertit avant le rendu.
  return text
    .replace(/<code>([^<`]*)<\/code>/gi, "`$1`")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/\[S(\d+)\]/g, (_, n) => `[${n}](#cite-S${n})`);
}

export function AnswerBody({ text, sources, onCite, streaming }:
  { text: string; sources: Source[]; onCite: (s: Source) => void; streaming?: boolean }) {
  return (
    <div className={`answer ${streaming ? "caret" : ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
        a({ href, children }) {
          if (href?.startsWith("#cite-")) {
            const src = sources.find((s) => s.source_id === href.slice(6));
            if (!src) return <sup className="cite cursor-default opacity-60">{children}</sup>;
            return (
              <button type="button" className="cite" onClick={() => onCite(src)}
                title={`${src.filename}${src.page ? ` — p. ${src.page}` : ""}`}
                aria-label={`Source ${children} : ${src.filename}${src.page ? `, page ${src.page}` : ""}`}>{children}</button>
            );
          }
          return <a href={href} target="_blank" rel="noreferrer" className="text-brand-700 underline">{children}</a>;
        },
      }}>{withCitations(text)}</ReactMarkdown>
    </div>
  );
}

export function SourceCards({ sources, onCite }: { sources: Source[]; onCite: (s: Source) => void }) {
  if (!sources.length) return null;
  return (
    <div className="mt-3 border-t border-[#eeecf6] pt-3">
      <p className="mb-2 text-sm font-semibold">Sources ({sources.length})</p>
      <div className="flex flex-wrap gap-2">
        {sources.map((s) => (
          <button key={s.source_id} type="button" onClick={() => onCite(s)} title={s.excerpt}
            className={`flex max-w-full items-center gap-2 rounded-xl border px-2.5 py-1.5 text-left text-xs transition hover:border-brand-300 hover:bg-brand-50 ${
              s.available ? "border-[#e3e0f0] bg-white" : "border-dashed border-slate-300 bg-slate-50 text-ink-500"}`}>
            <span className="cite !mx-0 !translate-y-0">{s.source_id.slice(1)}</span>
            <DocIcon filename={s.filename} size={22} />
            <span className="min-w-0">
              <span className="block max-w-[220px] truncate font-medium">{s.filename}</span>
              <span className="block text-[11px] text-ink-500">
                {s.available ? (s.page ? `p. ${s.page}` : s.section ?? "extrait") : "document supprimé"}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function AssistantMessage({ msg, onCite }: { msg: ChatMessage; onCite: (s: Source) => void }) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState(msg.feedback);
  const vote = (v: 1 | -1) => {
    const next = feedback === v ? 0 : v;
    setFeedback(next || null);
    api.feedback(msg.id, next as -1 | 0 | 1).catch(() => setFeedback(feedback));
  };
  const copy = () => {
    navigator.clipboard.writeText(msg.content.replace(/\[S(\d+)\]/g, "[$1]")).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <div>
      {msg.status === "no_answer" && (
        <div className="mb-2 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <SearchX size={16} className="mt-0.5 shrink-0" />
          <span>Aucun extrait pertinent n'a été trouvé dans vos documents pour cette question.</span>
        </div>
      )}
      {msg.status === "uncertain" && (
        <div className="mb-2 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <span>Réponse incertaine : aucune citation vérifiable. Contrôlez l'information dans vos documents.</span>
        </div>
      )}
      {msg.status === "error"
        ? <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{msg.content}</p>
        : <AnswerBody text={msg.content} sources={msg.sources} onCite={onCite} streaming={msg.streaming} />}
      {!msg.streaming && <SourceCards sources={msg.sources} onCite={onCite} />}
      {!msg.streaming && msg.status !== "error" && (
        <div className="mt-2 flex items-center gap-1">
          <button className="icon-btn" onClick={copy} aria-label="Copier la réponse" title="Copier">
            {copied ? <Check size={16} className="text-emerald-600" /> : <Copy size={16} />}
          </button>
          <button className={`icon-btn ${feedback === 1 ? "bg-brand-50 text-brand-700" : ""}`} onClick={() => vote(1)}
            aria-label="Réponse utile" aria-pressed={feedback === 1}><ThumbsUp size={16} /></button>
          <button className={`icon-btn ${feedback === -1 ? "bg-red-50 text-red-600" : ""}`} onClick={() => vote(-1)}
            aria-label="Réponse inutile" aria-pressed={feedback === -1}><ThumbsDown size={16} /></button>
        </div>
      )}
    </div>
  );
}
