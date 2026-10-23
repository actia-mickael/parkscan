import type { ReactNode } from "react";

import type { Decision, PassageStatus, ReviewStatus } from "@/types/api";
import { DECISION_LABELS, REVIEW_STATUS_LABELS, STATUS_LABELS } from "@/lib/format";

export function PageTitle({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-100">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-slate-800 bg-slate-900 p-5 ${className}`}>{children}</section>;
}

export function StatTile({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-100">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

const badgeBase = "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium";

export function DecisionBadge({ decision }: { decision: Decision }) {
  const cls = decision === "allowed" ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300";
  return <span className={`${badgeBase} ${cls}`}>{DECISION_LABELS[decision]}</span>;
}

export function StatusBadge({ status }: { status: PassageStatus }) {
  const cls = status === "ok" ? "bg-slate-700 text-slate-200" : "bg-amber-500/15 text-amber-300";
  return <span className={`${badgeBase} ${cls}`}>{STATUS_LABELS[status]}</span>;
}

export function ReviewBadge({ status }: { status: ReviewStatus }) {
  const cls =
    status === "pending"
      ? "bg-amber-500/15 text-amber-300"
      : status === "rejected"
        ? "bg-red-500/15 text-red-300"
        : "bg-emerald-500/15 text-emerald-300";
  return <span className={`${badgeBase} ${cls}`}>{REVIEW_STATUS_LABELS[status]}</span>;
}

export function Button({
  children,
  variant = "primary",
  type = "button",
  disabled,
  onClick,
  className = "",
}: {
  children: ReactNode;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  type?: "button" | "submit";
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  const variants = {
    primary: "bg-sky-600 hover:bg-sky-500 text-white",
    secondary: "bg-slate-800 hover:bg-slate-700 text-slate-100 border border-slate-700",
    danger: "bg-red-600/80 hover:bg-red-500 text-white",
    ghost: "text-slate-300 hover:bg-slate-800",
  };
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

export const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none";

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-slate-400">{label}</span>
      {children}
    </label>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="rounded-lg border border-dashed border-slate-800 p-6 text-center text-sm text-slate-500">{children}</p>;
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return <p className="mb-4 rounded-lg border border-red-900 bg-red-950/60 px-3 py-2 text-sm text-red-300">{message}</p>;
}

export function Pagination({
  page,
  size,
  total,
  onChange,
}: {
  page: number;
  size: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / size));
  if (pages <= 1) return null;
  return (
    <div className="mt-4 flex items-center justify-between text-sm text-slate-400">
      <span>
        Page {page} / {pages} · {total} éléments
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          Précédent
        </Button>
        <Button variant="secondary" disabled={page >= pages} onClick={() => onChange(page + 1)}>
          Suivant
        </Button>
      </div>
    </div>
  );
}

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800">
      <table className="min-w-full divide-y divide-slate-800 text-sm">
        <thead className="bg-slate-900/80 text-left text-xs uppercase tracking-wide text-slate-400">
          <tr>
            {head.map((h) => (
              <th key={h} className="px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/80 bg-slate-900/40">{children}</tbody>
      </table>
    </div>
  );
}
