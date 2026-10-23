import { create } from "zustand";

import { sitesApi } from "@/api/endpoints";
import type { SiteRead } from "@/types/api";

const CURRENT_KEY = "parkscan.site";

interface SiteState {
  sites: SiteRead[];
  currentSiteId: string | null; // null : tous les sites du périmètre
  loaded: boolean;
}

interface SiteActions {
  load: () => Promise<void>;
  setCurrent: (id: string | null) => void;
  reset: () => void;
}

function readCurrent(): string | null {
  try {
    return localStorage.getItem(CURRENT_KEY);
  } catch {
    return null;
  }
}

export const useSiteStore = create<SiteState & SiteActions>((set, get) => ({
  sites: [],
  currentSiteId: readCurrent(),
  loaded: false,

  load: async () => {
    const response = await sitesApi.list();
    const sites = response.data;
    const current = get().currentSiteId;
    const stillValid = current !== null && sites.some((s) => s.id === current);
    set({ sites, loaded: true, currentSiteId: stillValid ? current : null });
  },

  setCurrent: (id) => {
    try {
      if (id) localStorage.setItem(CURRENT_KEY, id);
      else localStorage.removeItem(CURRENT_KEY);
    } catch {
      // préférence non persistée
    }
    set({ currentSiteId: id });
  },

  reset: () => set({ sites: [], loaded: false }),
}));
