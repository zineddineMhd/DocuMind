import { Check, Download, MessageSquare, MessageSquarePlus, Pencil, Search, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Empty, Modal, PageHeader } from "../components/ui";
import { useApp } from "../hooks/useApp";
import { api, formatDate } from "../services/api";
import type { Conversation } from "../types";

export default function History() {
  const { workspace, fail, notify, refreshStats } = useApp();
  const navigate = useNavigate();
  const [convs, setConvs] = useState<Conversation[] | null>(null);
  const [text, setText] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [confirm, setConfirm] = useState<Conversation | null>(null);

  const load = useCallback(() => {
    if (workspace) api.conversations(workspace.id).then(setConvs).catch(fail);
  }, [workspace, fail]);
  useEffect(() => { setConvs(null); load(); }, [load]);

  const rename = async (c: Conversation) => {
    if (draft.trim() && draft.trim() !== c.title) {
      try { await api.renameConversation(c.id, draft.trim()); load(); } catch (e) { fail(e); }
    }
    setEditing(null);
  };
  const remove = async (c: Conversation) => {
    try { await api.deleteConversation(c.id); notify("Conversation supprimée.", "success"); load(); refreshStats().catch(() => {}); }
    catch (e) { fail(e); } finally { setConfirm(null); }
  };
  const exportMd = async (c: Conversation) => {
    try {
      const md = await api.exportConversation(c.id);
      const url = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
      const a = document.createElement("a");
      a.href = url; a.download = `${c.title.slice(0, 50).replace(/[\\/:*?"<>|]/g, "_")}.md`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { fail(e); }
  };

  const shown = (convs ?? []).filter((c) => c.title.toLowerCase().includes(text.toLowerCase()));

  return (
    <div className="mx-auto max-w-4xl p-5 lg:p-8">
      <PageHeader title="Historique" subtitle={`Conversations de l'espace « ${workspace?.name ?? ""} »`}
        actions={<button className="btn-primary" onClick={() => navigate("/chat")}><MessageSquarePlus size={16} />Nouvelle conversation</button>} />
      <div className="relative mb-3">
        <Search size={16} className="absolute left-3 top-3 text-ink-300" />
        <input className="input !pl-9" placeholder="Rechercher une conversation…" value={text} onChange={(e) => setText(e.target.value)} aria-label="Rechercher une conversation" />
      </div>
      <div className="card">
        {convs !== null && shown.length === 0 ? (
          <Empty icon={<MessageSquare size={22} />} title="Aucune conversation">Vos échanges avec vos documents apparaîtront ici.</Empty>
        ) : (
          <ul className="divide-y divide-[#f0eef7]">
            {shown.map((c) => (
              <li key={c.id} className="flex items-center gap-3 px-4 py-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><MessageSquare size={18} /></span>
                <div className="min-w-0 flex-1">
                  {editing === c.id ? (
                    <form className="flex gap-1" onSubmit={(e) => { e.preventDefault(); rename(c); }}>
                      <input autoFocus className="input !py-1.5" value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={200} aria-label="Nouveau titre" />
                      <button className="icon-btn" aria-label="Valider"><Check size={16} /></button>
                      <button type="button" className="icon-btn" onClick={() => setEditing(null)} aria-label="Annuler"><X size={16} /></button>
                    </form>
                  ) : (
                    <Link to={`/chat/${c.id}`} className="block truncate font-medium hover:text-brand-700">{c.title}</Link>
                  )}
                  <p className="text-xs text-ink-500">{c.message_count} messages · dernière activité {formatDate(c.updated_at)}</p>
                </div>
                <button className="icon-btn" onClick={() => { setEditing(c.id); setDraft(c.title); }} aria-label="Renommer" title="Renommer"><Pencil size={16} /></button>
                <button className="icon-btn" onClick={() => exportMd(c)} aria-label="Exporter en Markdown" title="Exporter"><Download size={16} /></button>
                <button className="icon-btn hover:!bg-red-50 hover:!text-red-600" onClick={() => setConfirm(c)} aria-label="Supprimer" title="Supprimer"><Trash2 size={16} /></button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {confirm && (
        <Modal title="Supprimer cette conversation ?" onClose={() => setConfirm(null)}>
          <p className="text-sm text-ink-700">« {confirm.title} » et ses {confirm.message_count} messages seront définitivement supprimés.</p>
          <div className="mt-5 flex justify-end gap-2">
            <button className="btn-ghost" onClick={() => setConfirm(null)}>Annuler</button>
            <button className="btn bg-red-600 text-white hover:bg-red-700" onClick={() => remove(confirm)}>Supprimer</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
