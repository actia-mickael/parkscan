// Miroir des schémas Pydantic du backend (backend/app/schemas). À synchroniser manuellement.

export interface LiveResponse {
  status: "ok";
}

export interface HealthResponse {
  status: "ok" | "degraded";
  checks: Record<string, "ok" | "error">;
  version: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export type UserRole = "operator_admin" | "site_manager" | "agent";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface TenantSummary {
  id: string;
  name: string;
  slug: string;
}

export interface MeResponse {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  tenant: TenantSummary;
  site_ids: string[];
}

export interface SiteRead {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  address: string | null;
  timezone: string;
  settings: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
}

export interface SiteCreate {
  name: string;
  slug?: string;
  address?: string | null;
  timezone?: string;
  settings?: Record<string, unknown>;
}

export interface SiteUpdate {
  name?: string;
  address?: string | null;
  timezone?: string;
  settings?: Record<string, unknown>;
  is_active?: boolean;
}

export interface ApiKeyRead {
  id: string;
  site_id: string;
  name: string;
  key_prefix: string;
  last_used_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface ApiKeyCreated extends ApiKeyRead {
  secret: string;
}

export interface UserRead {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  last_login_at: string | null;
  site_ids: string[];
  created_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name?: string | null;
  role: UserRole;
  site_ids: string[];
}

export interface ResidentRead {
  id: string;
  tenant_id: string;
  site_id: string;
  last_name: string;
  first_name: string;
  email: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  postal_code: string | null;
  subscription: boolean;
  is_active: boolean;
  notes: string | null;
  created_at: string;
}

export interface ResidentCreate {
  site_id: string;
  last_name: string;
  first_name: string;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  city?: string | null;
  postal_code?: string | null;
  subscription?: boolean;
  notes?: string | null;
}

export interface VehicleRead {
  id: string;
  tenant_id: string;
  site_id: string;
  resident_id: string;
  plate_raw: string;
  plate_norm: string;
  declared_brand: string | null;
  declared_model: string | null;
  color: string | null;
  access_enabled: boolean;
  valid_from: string | null;
  valid_until: string | null;
  created_at: string;
}

export interface VehicleCreate {
  resident_id: string;
  plate: string;
  declared_brand?: string | null;
  declared_model?: string | null;
  color?: string | null;
  access_enabled?: boolean;
}

export type PassageStatus = "ok" | "no_plate" | "low_ocr_conf" | "ml_error";
export type Decision = "allowed" | "denied";

export interface PassageRead {
  id: string;
  tenant_id: string;
  site_id: string;
  vehicle_id: string | null;
  captured_at: string | null;
  received_at: string;
  client_request_id: string;
  status: PassageStatus;
  decision: Decision;
  decision_reason: string;
  plate_text: string | null;
  plate_norm: string | null;
  ocr_conf: number | null;
  det_conf: number | null;
  plate_bbox: number[] | null;
  vehicle_bbox: number[] | null;
  vehicle_class: string | null;
  brand_pred: string | null;
  brand_conf: number | null;
  brand_top3: [string, number][] | null;
  declared_brand_snapshot: string | null;
  is_mismatch: boolean;
  image_key: string | null;
  plate_crop_key: string | null;
  vehicle_crop_key: string | null;
  conditions: Record<string, unknown> | null;
  latency_ms: number | null;
  ml_latency_ms: number | null;
  model_versions: Record<string, string> | null;
}

export interface PassageDetail extends PassageRead {
  raw_result: Record<string, unknown> | null;
}

export interface PresignedImage {
  url: string;
  expires_in: number;
  kind: "full" | "plate" | "vehicle";
}

export type ReviewStatus = "pending" | "validated" | "rejected" | "exported";
export type ReviewOutcome = "predicted_correct" | "declared_correct" | "custom" | "rejected";

export interface MismatchRead {
  id: string;
  tenant_id: string;
  site_id: string;
  passage_id: string;
  vehicle_id: string | null;
  predicted_brand: string;
  predicted_conf: number;
  declared_brand: string | null;
  status: ReviewStatus;
  outcome: ReviewOutcome | null;
  final_brand: string | null;
  reviewer_id: string | null;
  reviewed_at: string | null;
  comment: string | null;
  source_crop_key: string | null;
  dataset_key: string | null;
  created_at: string;
  plate_norm: string | null;
  received_at: string | null;
}

export interface ValidateRequest {
  outcome: "predicted_correct" | "declared_correct" | "custom";
  final_brand?: string | null;
  update_vehicle?: boolean;
  comment?: string | null;
}

export interface MismatchStats {
  pending: number;
  validated: number;
  rejected: number;
  exported: number;
  validated_by_brand: Record<string, number>;
  min_dataset_size: number;
  ready_for_retraining: boolean;
}

export interface BrandCount {
  brand: string;
  count: number;
}

export interface HourlyPoint {
  hour: string;
  allowed: number;
  denied: number;
}

export interface DashboardSummary {
  period_hours: number;
  passages: number;
  allowed: number;
  denied: number;
  mismatches: number;
  failed: number;
  pending_reviews: number;
  latency_avg_ms: number | null;
  latency_p95_ms: number | null;
  top_brands: BrandCount[];
  hourly: HourlyPoint[];
}
