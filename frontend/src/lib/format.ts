import type { Decision, PassageStatus, ReviewOutcome, ReviewStatus, UserRole } from "@/types/api";

const dateTime = new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "medium" });
const time = new Intl.DateTimeFormat("fr-FR", { timeStyle: "short" });

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : "—";
}

export function formatHour(iso: string): string {
  return time.format(new Date(iso));
}

export function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${Math.round(value * 100)} %`;
}

export const REASON_LABELS: Record<string, string> = {
  whitelist_match: "Plaque autorisée",
  unknown_plate: "Plaque inconnue",
  no_plate_read: "Aucune plaque lue",
  access_disabled: "Accès désactivé",
  resident_inactive: "Résident inactif",
  out_of_validity: "Hors période de validité",
  low_ocr_conf: "Lecture peu sûre",
  ml_unavailable: "Service ML indisponible",
};

export const STATUS_LABELS: Record<PassageStatus, string> = {
  ok: "OK",
  no_plate: "Sans plaque",
  low_ocr_conf: "Lecture faible",
  ml_error: "Erreur ML",
};

export const DECISION_LABELS: Record<Decision, string> = {
  allowed: "Autorisé",
  denied: "Refusé",
};

export const ROLE_LABELS: Record<UserRole, string> = {
  operator_admin: "Administrateur",
  site_manager: "Gestionnaire de site",
  agent: "Agent",
};

export const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  pending: "À valider",
  validated: "Validé",
  rejected: "Rejeté",
  exported: "Exporté",
};

export const OUTCOME_LABELS: Record<ReviewOutcome, string> = {
  predicted_correct: "Prédiction correcte",
  declared_correct: "Déclaration correcte",
  custom: "Autre marque",
  rejected: "Rejeté",
};

export function reasonLabel(reason: string): string {
  return REASON_LABELS[reason] ?? reason;
}

export function isAnonymized(plate: string | null | undefined): boolean {
  return !!plate && plate.startsWith("anon:");
}

/** Plaque affichable : « anonymisée » quand la rétention l'a remplacée par un haché. */
export function plateLabel(plate: string | null | undefined, empty = "—"): string {
  if (!plate) return empty;
  return isAnonymized(plate) ? "anonymisée" : plate;
}
