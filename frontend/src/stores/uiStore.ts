import { create } from "zustand";

export interface Toast {
  id: number;
  kind: "success" | "error" | "info";
  message: string;
}

interface UiState {
  toasts: Toast[];
}

interface UiActions {
  notify: (kind: Toast["kind"], message: string) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;

export const useUiStore = create<UiState & UiActions>((set) => ({
  toasts: [],
  notify: (kind, message) => {
    const id = nextId++;
    set((state) => ({ toasts: [...state.toasts, { id, kind, message }] }));
    setTimeout(() => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })), 5000);
  },
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));
