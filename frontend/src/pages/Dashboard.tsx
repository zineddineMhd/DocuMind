import { ArrowRight, FileText, FolderClosed, Layers, MessageSquare, MessagesSquare, Zap } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { DocIcon, Empty, ImportButton, PageHeader, StatusBadge } from "../components/ui";
import { useApp } from "../hooks/useApp";
import { api, formatBytes, formatDate } from "../services/api";
import type { Conversation } from "../types";

function Stat({ icon, value, label, tone }: { icon: ReactNode; value: ReactNode; label: string; tone: string }) {
  return (
    <div className="card flex items-center gap-3.5 p-4">
      <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${tone}`}>{icon}</span>
      <div className="min-w-0">
        <p className="truncate text-xl font-bold leading-tight">{value}</p>
        <p className="truncate text-sm text-ink-500">{label}</p>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user, stats, documents, workspace, workspaces, fail } = useApp();
  const [convs, setConvs] = useState<Conversation[]>([]);
  useEffect(() => {
    if (workspace) api.conversations(workspace.id).then(setConvs).catch(fail);
  }, [workspace, fail]);
  const ready = documents.filter((d) => d.status === "ready").length;

  return (
    <div className="mx-auto max-w-6xl p-5 lg:p-8">
      <PageHeader title={`Bonjour${user?.name ? `, ${user.name.split(" ")[0]}` : ""} 👋`}
        subtitle="Importez vos documents, posez vos questions et obtenez des réponses sourcées, des résumés et des analyses."
        actions={<ImportButton />} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat icon={<FileText size={20} />} value={stats?.documents ?? "—"} label="Documents" tone="bg-brand-50 text-brand-600" />
        <Stat icon={<MessageSquare size={20} />} value={stats?.conversations ?? "—"} label="Conversations" tone="bg-sky-50 text-sky-600" />
        <Stat icon={<FolderClosed size={20} />} value={workspaces.length} label="Espaces de travail" tone="bg-emerald-50 text-emerald-600" />
        <Stat icon={<Zap size={20} />} value={stats?.questions ?? "—"} label="Questions posées" tone="bg-amber-50 text-amber-600" />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <section className="card p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Documents récents <span className="font-normal text-ink-500">· {workspace?.name}</span></h2>
            <Link to="/documents" className="text-sm font-semibold text-brand-700 hover:underline">Voir tout</Link>
          </div>
          {documents.length === 0 ? (
            <Empty icon={<FileText size={22} />} title="Aucun document">Importez un PDF, DOCX ou TXT pour commencer.</Empty>
          ) : (
            <ul className="divide-y divide-[#f0eef7]">
              {documents.slice(0, 5).map((d) => (
                <li key={d.id} className="flex items-center gap-3 py-2.5">
                  <DocIcon filename={d.filename} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{d.filename}</p>
                    <p className="text-xs text-ink-500">{formatBytes(d.file_size)} · Ajouté {formatDate(d.created_at)}</p>
                  </div>
                  <StatusBadge doc={d} />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Conversations récentes</h2>
            <Link to="/historique" className="text-sm font-semibold text-brand-700 hover:underline">Voir tout</Link>
          </div>
          {convs.length === 0 ? (
            <Empty icon={<MessagesSquare size={22} />} title="Aucune conversation">
              {ready ? "Posez votre première question à vos documents." : "Les conversations apparaîtront ici."}
            </Empty>
          ) : (
            <ul className="divide-y divide-[#f0eef7]">
              {convs.slice(0, 5).map((c) => (
                <li key={c.id}>
                  <Link to={`/chat/${c.id}`} className="group flex items-center gap-3 py-2.5">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><MessageSquare size={16} /></span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium group-hover:text-brand-700">{c.title}</p>
                      <p className="text-xs text-ink-500">{c.message_count} messages · {formatDate(c.updated_at)}</p>
                    </div>
                    <ArrowRight size={16} className="text-ink-300 group-hover:text-brand-600" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <Link to="/chat" className="card mt-5 flex items-center gap-4 bg-gradient-to-r from-brand-600 to-brand-500 p-5 text-white transition hover:from-brand-700 hover:to-brand-600">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/15"><Layers size={24} /></span>
        <div className="min-w-0 flex-1">
          <p className="text-lg font-semibold">Discuter avec vos documents</p>
          <p className="text-sm text-white/80">{ready} document(s) prêt(s) dans « {workspace?.name} » — recherche sémantique, résumés et citations des sources.</p>
        </div>
        <ArrowRight size={22} />
      </Link>
    </div>
  );
}
