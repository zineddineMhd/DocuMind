import { BookOpenCheck, Loader2, Quote, Search } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Logo } from "../components/Layout";
import { useApp } from "../hooks/useApp";
import { api } from "../services/api";

export default function Login() {
  const { signIn } = useApp();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (mode === "register" && password.length < 8) { setError("Le mot de passe doit contenir au moins 8 caractères."); return; }
    setBusy(true);
    try {
      const out = mode === "login" ? await api.login(email, password) : await api.register(email, password, name);
      signIn(out.access_token, out.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue.");
    } finally { setBusy(false); }
  };

  return (
    <div className="grid min-h-full lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-gradient-to-br from-[#17143a] via-[#231b57] to-[#4a31b3] p-12 text-white lg:flex">
        <Logo />
        <div>
          <h1 className="text-4xl font-bold leading-tight">Discutez avec vos documents,<br />sources à l'appui.</h1>
          <p className="mt-4 max-w-md text-white/70">Importez vos PDF, DOCX et TXT, posez vos questions en langage naturel et obtenez des réponses fondées sur des passages vérifiables.</p>
          <ul className="mt-8 space-y-4 text-sm text-white/85">
            <li className="flex items-center gap-3"><Search size={18} className="text-brand-300" />Recherche sémantique hybride dans vos espaces de travail</li>
            <li className="flex items-center gap-3"><Quote size={18} className="text-brand-300" />Citations cliquables jusqu'à la page du document</li>
            <li className="flex items-center gap-3"><BookOpenCheck size={18} className="text-brand-300" />Abstention explicite quand le corpus ne permet pas de répondre</li>
          </ul>
        </div>
        <p className="text-xs text-white/40">Les extraits utiles à une réponse sont transmis à l'API Gemini de Google pour la génération.</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="card w-full max-w-md p-8">
          <div className="mb-6 lg:hidden"><Logo light={false} /></div>
          <h2 className="text-2xl font-bold">{mode === "login" ? "Connexion" : "Créer un compte"}</h2>
          <p className="mt-1 text-sm text-ink-500">
            {mode === "login" ? "Accédez à vos espaces documentaires." : "Quelques secondes suffisent pour commencer."}
          </p>
          <div className="mt-6 space-y-4">
            {mode === "register" && (
              <div>
                <label htmlFor="name" className="mb-1 block text-sm font-medium">Nom</label>
                <input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jean Dupont" autoComplete="name" />
              </div>
            )}
            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-medium">Adresse e-mail</label>
              <input id="email" type="email" required className="input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="vous@exemple.com" autoComplete="email" />
            </div>
            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-medium">Mot de passe</label>
              <input id="password" type="password" required className="input" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === "register" ? "8 caractères minimum" : "••••••••"} autoComplete={mode === "login" ? "current-password" : "new-password"} />
            </div>
            {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            <button className="btn-primary w-full" disabled={busy}>
              {busy && <Loader2 size={16} className="animate-spin" />}{mode === "login" ? "Se connecter" : "Créer mon compte"}
            </button>
          </div>
          <p className="mt-6 text-center text-sm text-ink-500">
            {mode === "login" ? "Pas encore de compte ?" : "Déjà inscrit ?"}{" "}
            <button type="button" className="font-semibold text-brand-700 hover:underline"
              onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
              {mode === "login" ? "Créer un compte" : "Se connecter"}
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}
