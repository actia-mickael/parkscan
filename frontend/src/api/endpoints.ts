import type { AxiosResponse } from "axios";

import type {
  ApiKeyCreated,
  ApiKeyRead,
  DashboardSummary,
  HealthResponse,
  MeResponse,
  MismatchRead,
  MismatchStats,
  Page,
  PassageDetail,
  PassageRead,
  PresignedImage,
  ResidentCreate,
  ResidentRead,
  SiteCreate,
  SiteRead,
  SiteUpdate,
  UserCreate,
  UserRead,
  ValidateRequest,
  VehicleCreate,
  VehicleRead,
} from "@/types/api";

import { api } from "./client";

type Params = Record<string, string | number | boolean | undefined | null>;

export const healthApi = {
  get: (): Promise<AxiosResponse<HealthResponse>> => api.get("/health"),
};

export const authApi = {
  me: (): Promise<AxiosResponse<MeResponse>> => api.get("/auth/me"),
  logout: (refresh_token: string): Promise<AxiosResponse<void>> => api.post("/auth/logout", { refresh_token }),
};

export const dashboardApi = {
  summary: (params: Params): Promise<AxiosResponse<DashboardSummary>> => api.get("/dashboard/summary", { params }),
};

export const sitesApi = {
  list: (): Promise<AxiosResponse<SiteRead[]>> => api.get("/sites"),
  get: (id: string): Promise<AxiosResponse<SiteRead>> => api.get(`/sites/${id}`),
  create: (body: SiteCreate): Promise<AxiosResponse<SiteRead>> => api.post("/sites", body),
  update: (id: string, body: SiteUpdate): Promise<AxiosResponse<SiteRead>> => api.patch(`/sites/${id}`, body),
  keys: (id: string): Promise<AxiosResponse<ApiKeyRead[]>> => api.get(`/sites/${id}/api-keys`),
  createKey: (id: string, name: string): Promise<AxiosResponse<ApiKeyCreated>> =>
    api.post(`/sites/${id}/api-keys`, { name }),
  revokeKey: (keyId: string): Promise<AxiosResponse<void>> => api.delete(`/api-keys/${keyId}`),
};

export const usersApi = {
  list: (): Promise<AxiosResponse<UserRead[]>> => api.get("/users"),
  create: (body: UserCreate): Promise<AxiosResponse<UserRead>> => api.post("/users", body),
  update: (id: string, body: Partial<Pick<UserRead, "full_name" | "role" | "is_active">>): Promise<AxiosResponse<UserRead>> =>
    api.patch(`/users/${id}`, body),
};

export const residentsApi = {
  list: (params: Params): Promise<AxiosResponse<Page<ResidentRead>>> => api.get("/residents", { params }),
  get: (id: string): Promise<AxiosResponse<ResidentRead>> => api.get(`/residents/${id}`),
  create: (body: ResidentCreate): Promise<AxiosResponse<ResidentRead>> => api.post("/residents", body),
  update: (id: string, body: Partial<ResidentCreate> & { is_active?: boolean }): Promise<AxiosResponse<ResidentRead>> =>
    api.patch(`/residents/${id}`, body),
  remove: (id: string): Promise<AxiosResponse<void>> => api.delete(`/residents/${id}`),
  vehicles: (id: string): Promise<AxiosResponse<VehicleRead[]>> => api.get(`/residents/${id}/vehicles`),
};

export const vehiclesApi = {
  list: (params: Params): Promise<AxiosResponse<Page<VehicleRead>>> => api.get("/vehicles", { params }),
  create: (body: VehicleCreate): Promise<AxiosResponse<VehicleRead>> => api.post("/vehicles", body),
  toggleAccess: (id: string, enabled: boolean): Promise<AxiosResponse<VehicleRead>> =>
    api.post(`/vehicles/${id}/access`, { enabled }),
  remove: (id: string): Promise<AxiosResponse<void>> => api.delete(`/vehicles/${id}`),
};

export const passagesApi = {
  list: (params: Params): Promise<AxiosResponse<Page<PassageRead>>> => api.get("/passages", { params }),
  get: (id: string): Promise<AxiosResponse<PassageDetail>> => api.get(`/passages/${id}`),
  image: (id: string, kind: "full" | "plate" | "vehicle"): Promise<AxiosResponse<PresignedImage>> =>
    api.get(`/passages/${id}/image`, { params: { kind } }),
};

export const mismatchesApi = {
  list: (params: Params): Promise<AxiosResponse<Page<MismatchRead>>> => api.get("/mismatches", { params }),
  stats: (): Promise<AxiosResponse<MismatchStats>> => api.get("/mismatches/stats"),
  validate: (id: string, body: ValidateRequest): Promise<AxiosResponse<MismatchRead>> =>
    api.post(`/mismatches/${id}/validate`, body),
  reject: (id: string, comment?: string): Promise<AxiosResponse<MismatchRead>> =>
    api.post(`/mismatches/${id}/reject`, { comment: comment ?? null }),
};
