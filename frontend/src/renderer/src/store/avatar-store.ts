import { create } from 'zustand';

export type Emotion =
  | 'neutral'
  | 'happy'
  | 'surprised'
  | 'sad'
  | 'worried'
  | 'thinking'
  | 'sleepy'
  | 'study';

export interface AvatarState {
  emotion: Emotion;
  crossfadeMs: number;
  speaking: boolean;
}

export interface AvatarActions {
  setAvatarState: (state: Partial<AvatarState>) => void;
}

export const useAvatarStore = create<AvatarState & AvatarActions>((set) => ({
  emotion: 'neutral',
  crossfadeMs: 250,
  speaking: false,
  setAvatarState: (newState: Partial<AvatarState>) => set((prev) => ({ ...prev, ...newState })),
}));
