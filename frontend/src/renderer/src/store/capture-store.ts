import { create } from 'zustand';

export interface CaptureState {
  running: boolean;
  intervalSec: number;
}

export interface CaptureActions {
  setRunning: (running: boolean) => void;
  setIntervalSec: (intervalSec: number) => void;
}

export const useCaptureStore = create<CaptureState & CaptureActions>((set) => ({
  running: false,
  intervalSec: 30,
  setRunning: (running: boolean) => set({ running }),
  setIntervalSec: (intervalSec: number) => set({ intervalSec }),
}));
