import { useEffect, useState } from "react";

import { getHealth } from "./api/health";
import type { HealthResponse } from "./types/api";

type Status = { kind: "loading" } | { kind: "ok"; data: HealthResponse } | { kind: "error"; message: string };

export default function App() {
  const [status, setStatus] = useState<Status>({ kind: "loading" });

  useEffect(() => {
    getHealth()
      .then((res) => setStatus({ kind: "ok", data: res.data }))
      .catch((err: unknown) =>
        setStatus({ kind: "error", message: err instanceof Error ? err.message : "erreur inconnue" }),
      );
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
      <div className="max-w-md w-full rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-xl">
        <h1 className="text-3xl font-semibold tracking-tight">ParkScan AI</h1>
        <p className="mt-2 text-slate-400">Back-office opérateur</p>

        <section className="mt-6 rounded-xl bg-slate-800/60 p-4 text-sm">
          <h2 className="font-medium text-slate-200">État de l'API</h2>
          {status.kind === "loading" && <p className="mt-2 text-slate-400">Vérification…</p>}
          {status.kind === "error" && <p className="mt-2 text-red-400">Injoignable : {status.message}</p>}
          {status.kind === "ok" && (
            <ul className="mt-2 space-y-1">
              <li>
                Statut : <span className={status.data.status === "ok" ? "text-emerald-400" : "text-amber-400"}>{status.data.status}</span>
              </li>
              <li>Version : {status.data.version}</li>
              {Object.entries(status.data.checks).map(([name, value]) => (
                <li key={name}>
                  {name} : <span className={value === "ok" ? "text-emerald-400" : "text-red-400"}>{value}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
