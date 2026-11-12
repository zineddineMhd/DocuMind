import { Check, FolderClosed, FolderPlus, Pencil, Trash2, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Modal, PageHeader } from "../components/ui";
import { useApp } from "../hooks/useApp";
import { api, formatDate } from "../services/api";
import type { Workspace } from "../types";

export default function Collections() {
  const { workspaces, workspace, selectWorkspace, refreshWorkspaces, refreshStats, notify, fail } = useApp();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [confirm, setConfirm] = useState<Workspace | null>(null);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const ws = await api.createWorkspace(name.trim());
      setName(""); await refreshWorkspaces(); selectWorkspace(ws.id);
      notify(`Espace « ${ws.name} » créé.`, "success"); refreshStats().catch(() => {});
    } catch (err) { fail(err); }
  };
  const rename = async (w: Workspace) => {
    if (draft.trim() && draft.trim() !== w.name) {
      try { await api.renameWorkspace(w.id, draft.trim()); await refreshWorkspaces(); } catch (e) { fail(e); }
    }
    setEditing(null);
  };
  const remove = async (w: Workspace) => {
    try {
      await api.deleteWorkspace(w.id); await refreshWorkspaces(); refreshStats().catch(() => {});
      notify(`Espace « ${w.name} » supprimé.`, "success");
    } catch (e) { fail(e); } finally { setConfirm(null); }
  };

  return (
    <div className="mx-auto max-w-5xl p-5 lg:p-8">
      <PageHeader title="Collections" subtitle="Organisez vos documents par espace de travail : chaque espace a ses fichiers et ses conversations." />
      <form onSubmit={create} className="card mb-5 flex flex-wrap gap-2 p-4">
        <input className="input min-w-[200px] flex-1" placeholder="Nom du nouvel espace (ex. Réseaux, Rapports 2024…)" value={name}
          onChange={(e) => setName(e.target.value)} maxLength={120} aria-label="Nom du nouvel espace" />
        <button className="btn-primary" disabled={!name.trim()}><FolderPlus size={16} />Créer un espace</button>
      </form>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {workspaces.map((w) => {
          const active = w.id === workspace?.id;
          return (
            <div key={w.id} className={`card flex flex-col p-4 ${active ? "ring-2 ring-brand-400" : ""}`}>
              <div className="flex items-start gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><FolderClosed size={20} /></span>
                <div className="min-w-0 flex-1">
                  {editing === w.id ? (
                    <form className="flex gap-1" onSubmit={(e) => { e.preventDefault(); rename(w); }}>
                      <input autoFocus className="input !py-1.5" value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={120} aria-label="Nouveau nom" />
                      <button className="icon-btn" aria-label="Valider"><Check size={16} /></button>
                      <button type="button" className="icon-btn" onClick={() => setEditing(null)} aria-label="Annuler"><X size={16} /></button>
                    </form>
                  ) : <p className="truncate font-semibold">{w.name}</p>}
                  <p className="text-xs text-ink-500">Créé {formatDate(w.created_at)}</p>
                </div>
                {active && <span className="chip shrink-0">Actif</span>}
              </div>
              <p className="mt-3 text-sm text-ink-700">{w.document_count} document(s) · {w.conversation_count} conversation(s)</p>
              <div className="mt-4 flex items-center gap-1">
                <button className={active ? "btn-ghost flex-1 !py-2" : "btn-primary flex-1 !py-2"}
                  onClick={() => { selectWorkspace(w.id); navigate("/documents"); }}>{active ? "Ouvrir" : "Activer et ouvrir"}</button>
                <button className="icon-btn" onClick={() => { setEditing(w.id); setDraft(w.name); }} aria-label={`Renommer ${w.name}`} title="Renommer"><Pencil size={16} /></button>
                <button className="icon-btn hover:!bg-red-50 hover:!text-red-600" disabled={workspaces.length <= 1}
                  title={workspaces.length <= 1 ? "Conservez au moins un espace" : "Supprimer"} onClick={() => setConfirm(w)} aria-label={`Supprimer ${w.name}`}><Trash2 size={16} /></button>
              </div>
            </div>
          );
        })}
      </div>
      {confirm && (
        <Modal title="Supprimer cet espace ?" onClose={() => setConfirm(null)}>
          <p className="text-sm text-ink-700">L'espace « {confirm.name} », ses {confirm.document_count} document(s) et ses {confirm.conversation_count} conversation(s) seront définitivement supprimés.</p>
          <div className="mt-5 flex justify-end gap-2">
            <button className="btn-ghost" onClick={() => setConfirm(null)}>Annuler</button>
            <button className="btn bg-red-600 text-white hover:bg-red-700" onClick={() => remove(confirm)}>Supprimer</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
