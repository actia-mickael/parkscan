import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import { useAuthStore } from "@/stores/authStore";

export const api = axios.create({
  baseURL: "/api/v1",
  timeout: 15_000,
});

type RetriableConfig = InternalAxiosRequestConfig & { _retry?: boolean };

// Un seul rafraîchissement à la fois : les requêtes concurrentes en 401 attendent le même jeton.
let refreshing: Promise<string | null> | null = null;

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const original = error.config as RetriableConfig | undefined;
  const isAuthCall = original?.url?.startsWith("/auth/") ?? false;
  if (error.response?.status === 401 && original && !original._retry && !isAuthCall) {
    original._retry = true;
    refreshing ??= useAuthStore
      .getState()
      .refresh()
      .finally(() => {
        refreshing = null;
      });
    const token = await refreshing;
    if (token) {
      original.headers.Authorization = `Bearer ${token}`;
      return api(original);
    }
  }
  return Promise.reject(error);
});

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => String((d as { msg?: string }).msg ?? d)).join(", ");
    return error.message;
  }
  return error instanceof Error ? error.message : "Erreur inconnue";
}
