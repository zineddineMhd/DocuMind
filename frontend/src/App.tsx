import { Loader2 } from "lucide-react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useApp } from "./hooks/useApp";
import Chat from "./pages/Chat";
import Collections from "./pages/Collections";
import Dashboard from "./pages/Dashboard";
import Documents from "./pages/Documents";
import History from "./pages/History";
import Login from "./pages/Login";
import Settings from "./pages/Settings";

export default function App() {
  const { user, booting } = useApp();
  if (booting) {
    return <div className="flex h-full items-center justify-center text-brand-600"><Loader2 className="animate-spin" size={28} /></div>;
  }
  if (!user) return <Login />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="chat" element={<Chat />} />
        <Route path="chat/:conversationId" element={<Chat />} />
        <Route path="documents" element={<Documents />} />
        <Route path="historique" element={<History />} />
        <Route path="collections" element={<Collections />} />
        <Route path="parametres" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
