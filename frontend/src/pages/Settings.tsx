import { Cpu, Gauge, ShieldAlert, UserRound } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Modal, PageHeader } from "../components/ui";
import { useApp } from "../hooks/useApp";
import { api, formatBytes } from "../services/api";

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2 text-sm">
      <span className="text-ink-500">{label}</span><span className="text-right font-medium">{children}</span>
    </div>
  );
}

export default function Settings() {
  const { user, setUser, stats, signOut, notify, fail } = useApp();
  const [name, setName] = useState(user?.name ?? "");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const c = stats?.config;

  const saveProfile = async (e: FormEvent) => {
    e.preventDefault();
    try { setUser(await api.updateMe({ name })); notify("Profil mis à jour.", "success"); } catch (err) { fail(err); }
  };
  const savePassword = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.updateMe({ current_password: current, new_password: next });
      setCurrent(""); setNext(""); notify("Mot de passe modifié.", "success");
    } catch (err) { fail(err); }
  };
  const deleteAccount = async () => {
    try { await api.deleteMe(); signOut(); } catch (err) { fail(err); }
  };

  return (
    <div className="mx-auto max-w-4xl p-5 lg:p-8">
      <PageHeader title="Paramètres" subtitle="Profil, configuration du serveur, quotas et suppression des données." />
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="card p-5">
          <h2 className="mb-3 flex items-center gap-2 font-semibold"><UserRound size={18} className="text-brand-600" />Profil</h2>
          <form onSubmit={saveProfile} className="space-y-3">
            <div>
              <label className="mb-1 block text-sm font-medium" htmlFor="s-email">Adresse e-mail</label>
              <input id="s-email" className="input bg-slate-50" value={user?.email ?? ""} disabled />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium" htmlFor="s-name">Nom</label>
              <input id="s-name" className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
            </div>
            <button className="btn-primary" disabled={!name.trim() || name === user?.name}>Enregistrer</button>
          </form>
          <form onSubmit={savePassword} className="mt-6 space-y-3 border-t border-[#eeecf6] pt-5">
            <p className="text-sm font-semibold">Changer de mot de passe</p>
            <input type="password" className="input" placeholder="Mot de passe actuel" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" aria-label="Mot de passe actuel" />
            <input type="password" className="input" placeholder="Nouveau mot de passe (8 caractères minimum)" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" aria-label="Nouveau mot de passe" />
            <button className="btn-ghost" disabled={!current || next.length < 8}>Modifier le mot de passe</button>
          </form>
        </section>

        <div className="space-y-5">
          <section className="card p-5">
            <h2 className="mb-2 flex items-center gap-2 font-semibold"><Cpu size={18} className="text-brand-600" />Modèles (configurés côté serveur)</h2>
            <div className="divide-y divide-[#f0eef7]">
              <Row label="Modèle de génération">{c?.gemini_model ?? "—"}</Row>
              <Row label="Clé API Gemini">{c ? (c.gemini_configured
                ? <span className="text-emerald-700">Configurée</span> : <span className="text-red-600">Absente</span>) : "—"}</Row>
              <Row label="Modèle d'embeddings"><span className="break-all">{c?.embedding_version ?? "—"}</span></Row>
              <Row label="Recherche">{c ? (c.hybrid_search ? "Hybride (vecteurs + BM25)" : "Vectorielle") + (c.reranker ? " + reranking" : "") : "—"}</Row>
              <Row label="Passages par réponse">{c?.top_k ?? "—"}</Row>
            </div>
            <p className="mt-3 text-xs text-ink-500">Les extraits utiles à une réponse sont transmis à l'API Gemini (Google). N'importez pas de données confidentielles sans avoir vérifié les conditions applicables.</p>
          </section>

          <section className="card p-5">
            <h2 className="mb-2 flex items-center gap-2 font-semibold"><Gauge size={18} className="text-brand-600" />Quotas et utilisation</h2>
            <div className="divide-y divide-[#f0eef7]">
              <Row label="Stockage utilisé">{stats ? `${formatBytes(stats.storage_used)} / ${formatBytes(stats.storage_quota)}` : "—"}</Row>
              <Row label="Taille maximale par fichier">{c ? `${c.max_upload_mb} Mo` : "—"}</Row>
              <Row label="Questions par minute">{c?.rate_limit_chat_per_min ?? "—"}</Row>
              <Row label="Questions posées">{stats?.questions ?? "—"}</Row>
              <Row label="Taux d'abstention">{stats ? `${(stats.abstention_rate * 100).toFixed(0)} %` : "—"}</Row>
            </div>
          </section>

          <section className="card border-red-100 p-5">
            <h2 className="mb-2 flex items-center gap-2 font-semibold text-red-700"><ShieldAlert size={18} />Suppression des données</h2>
            <p className="text-sm text-ink-700">Supprime définitivement votre compte, vos espaces, documents, vecteurs et conversations.</p>
            <button className="btn-danger mt-3" onClick={() => setConfirm(true)}>Supprimer mon compte</button>
          </section>
        </div>
      </div>
      {confirm && (
        <Modal title="Supprimer définitivement le compte ?" onClose={() => setConfirm(false)}>
          <p className="text-sm text-ink-700">Cette action est irréversible. Saisissez <strong>SUPPRIMER</strong> pour confirmer.</p>
          <input className="input mt-3" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} aria-label="Confirmation" />
          <div className="mt-5 flex justify-end gap-2">
            <button className="btn-ghost" onClick={() => setConfirm(false)}>Annuler</button>
            <button className="btn bg-red-600 text-white hover:bg-red-700" disabled={confirmText !== "SUPPRIMER"} onClick={deleteAccount}>Supprimer mon compte</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
