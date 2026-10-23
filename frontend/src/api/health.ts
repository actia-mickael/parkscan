import type { AxiosResponse } from "axios";

import type { HealthResponse, LiveResponse } from "../types/api";
import { api } from "./client";

export function getLive(): Promise<AxiosResponse<LiveResponse>> {
  return api.get<LiveResponse>("/health/live");
}

export function getHealth(): Promise<AxiosResponse<HealthResponse>> {
  return api.get<HealthResponse>("/health");
}
