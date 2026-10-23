import axios from "axios";
import { create } from "zustand";

import type { MeResponse, TokenPair } from "@/types/api";

const REFRESH_KEY = "parkscan.refresh";

function readRefresh(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

function writeRefresh(token: string | null): void {
  try {
    if (token) localStorage.setItem(REFRESH_KEY, token);
    else localStorage.removeItem(REFRESH_KEY);
  } catch {
    // stockage indisponible (navigation privée) : la session ne survivra pas au rechargement
  }
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: MeResponse | null;
  status: "idle" | "loading" | "ready";
}

interface AuthActions {
  bootstrap: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<string | null>;
}

// Appels d'authentification hors intercepteur (pas de boucle de rafraîchissement).
const bare = axios.create({ baseURL: "/api/v1", timeout: 10_000 });

export const useAuthStore = create<AuthState & AuthActions>((set, get) => ({
  accessToken: null,
  refreshToken: readRefresh(),
  user: null,
  status: "idle",

  bootstrap: async () => {
    set({ status: "loading" });
    const token = await get().refresh();
    if (!token) {
      set({ status: "ready", user: null });
      return;
    }
    try {
      const me = await bare.get<MeResponse>("/auth/me", { headers: { Authorization: `Bearer ${token}` } });
      set({ user: me.data, status: "ready" });
    } catch {
      set({ user: null, accessToken: null, status: "ready" });
    }
  },

  login: async (email, password) => {
    const tokens = await bare.post<TokenPair>("/auth/login", { email, password });
    writeRefresh(tokens.data.refresh_token);
    const me = await bare.get<MeResponse>("/auth/me", {
      headers: { Authorization: `Bearer ${tokens.data.access_token}` },
    });
    set({
      accessToken: tokens.data.access_token,
      refreshToken: tokens.data.refresh_token,
      user: me.data,
      status: "ready",
    });
  },

  logout: async () => {
    const refreshToken = get().refreshToken;
    if (refreshToken) {
      try {
        await bare.post("/auth/logout", { refresh_token: refreshToken });
      } catch {
        // le jeton est de toute façon abandonné côté client
      }
    }
    writeRefresh(null);
    set({ accessToken: null, refreshToken: null, user: null, status: "ready" });
  },

  refresh: async () => {
    const refreshToken = get().refreshToken;
    if (!refreshToken) return null;
    try {
      const tokens = await bare.post<TokenPair>("/auth/refresh", { refresh_token: refreshToken });
      writeRefresh(tokens.data.refresh_token);
      set({ accessToken: tokens.data.access_token, refreshToken: tokens.data.refresh_token });
      return tokens.data.access_token;
    } catch {
      writeRefresh(null);
      set({ accessToken: null, refreshToken: null, user: null });
      return null;
    }
  },
}));
