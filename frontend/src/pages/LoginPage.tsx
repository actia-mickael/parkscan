import { type FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { Button, ErrorBanner, Field, inputClass } from "@/components/ui";
import { useAuthStore } from "@/stores/authStore";

export default function LoginPage() {
  const login = useAuthStore((s) => s.login);
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-xl">
        <h1 className="text-2xl font-semibold tracking-tight">ParkScan AI</h1>
        <p className="mb-6 mt-1 text-sm text-slate-400">Back-office opérateur</p>
        <ErrorBanner message={error} />
        <div className="space-y-4">
          <Field label="Adresse e-mail">
            <input className={inputClass} type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </Field>
          <Field label="Mot de passe">
            <input
              className={inputClass}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Field>
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Connexion…" : "Se connecter"}
          </Button>
        </div>
      </form>
    </main>
  );
}
