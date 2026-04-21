import { create } from 'zustand';

export interface DndState {
  enabled: boolean;
}

export interface DndActions {
  setEnabled: (enabled: boolean) => void;
}

export const useDndStore = create<DndState & DndActions>((set) => ({
  enabled: false,
  setEnabled: (enabled: boolean) => set({ enabled }),
}));
