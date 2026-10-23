// Miroir des schémas Pydantic du backend (backend/app/schemas). À synchroniser manuellement.

export interface LiveResponse {
  status: "ok";
}

export interface HealthResponse {
  status: "ok" | "degraded";
  checks: Record<string, "ok" | "error">;
  version: string;
}
