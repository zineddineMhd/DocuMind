import { AlertCircle, CheckCircle2, Clock, FileText, Loader2, UploadCloud, X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { useApp } from "../hooks/useApp";
import type { Doc, DocStatus } from "../types";

export const ACCEPT = ".pdf,.docx,.txt,.md";

export function DocIcon({ filename, size = 36 }: { filename: string; size?: number }) {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  const style: Record<string, [string, string]> = {
    pdf: ["bg-red-50 text-red-600 border-red-100", "PDF"],
    docx: ["bg-blue-50 text-blue-600 border-blue-100", "W"],
    txt: ["bg-slate-50 text-slate-600 border-slate-200", "TXT"],
    md: ["bg-violet-50 text-violet-600 border-violet-100", "MD"],
  };
  const [cls, label] = style[ext] ?? ["bg-slate-50 text-slate-500 border-slate-200", ""];
  return (
    <span className={`inline-flex shrink-0 items-center justify-center rounded-lg border font-bold ${cls}`}
      style={{ width: size, height: size, fontSize: Math.max(9, size / 3.6) }} aria-hidden>
      {label || <FileText size={size / 2} />}
    </span>
  );
}

const STATUS: Record<DocStatus, { label: string; cls: string; icon: ReactNode }> = {
  pending: { label: "En attente", cls: "bg-slate-100 text-slate-600", icon: <Clock size={12} /> },
  processing: { label: "Indexation en cours", cls: "bg-amber-50 text-amber-700", icon: <Loader2 size={12} className="animate-spin" /> },
  ready: { label: "Prêt", cls: "bg-emerald-50 text-emerald-700", icon: <CheckCircle2 size={12} /> },
  failed: { label: "Échec", cls: "bg-red-50 text-red-700", icon: <AlertCircle size={12} /> },
};

export function StatusBadge({ doc, compact = false }: { doc: Doc; compact?: boolean }) {
  const s = STATUS[doc.status];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${s.cls}`}
      title={doc.error ?? s.label}>
      {s.icon}{!compact && s.label}
    </span>
  );
}

export function Modal({ title, onClose, children, wide = false }:
  { title: ReactNode; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/40 p-3 backdrop-blur-sm" onMouseDown={onClose}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true"
        className={`card flex max-h-[92vh] w-full flex-col outline-none ${wide ? "max-w-6xl" : "max-w-lg"}`}
        onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between gap-3 border-b border-[#eeecf6] px-5 py-3.5">
          <h2 className="min-w-0 truncate text-base font-semibold">{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Fermer"><X size={18} /></button>
        </div>
        <div className="scroll-thin min-h-0 flex-1 overflow-auto p-5">{children}</div>
      </div>
    </div>
  );
}

export function Toasts() {
  const { toasts } = useApp();
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(92vw,380px)] flex-col gap-2" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} role="status"
          className={`pointer-events-auto flex items-start gap-2 rounded-xl border px-4 py-3 text-sm shadow-card ${
            t.kind === "error" ? "border-red-200 bg-red-50 text-red-800"
              : t.kind === "success" ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-[#e3e0f0] bg-white text-ink-700"}`}>
          {t.kind === "error" ? <AlertCircle size={16} className="mt-0.5 shrink-0" />
            : t.kind === "success" ? <CheckCircle2 size={16} className="mt-0.5 shrink-0" /> : null}
          <span>{t.text}</span>
        </div>
      ))}
    </div>
  );
}

export function ImportButton({ className = "btn-primary", label = "Importer des documents" }:
  { className?: string; label?: string }) {
  const { uploadFiles, uploading, workspace } = useApp();
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input ref={input} type="file" accept={ACCEPT} multiple hidden
        onChange={(e) => { uploadFiles(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
      <button className={className} disabled={uploading || !workspace} onClick={() => input.current?.click()}>
        {uploading ? <Loader2 size={16} className="animate-spin" /> : <UploadCloud size={16} />}{label}
      </button>
    </>
  );
}

export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">{icon}</span>
      <p className="font-semibold">{title}</p>
      {children && <div className="max-w-sm text-sm text-ink-500">{children}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
